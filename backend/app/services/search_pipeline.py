from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import latest_context, latest_profile
from app.database import session as database
from app.integrations import SourceError, get_source
from app.models import (
    AuditEvent,
    ContextVersion,
    Evaluation,
    Job,
    ProfileVersion,
    SearchRun,
    SourceCache,
    User,
)
from app.schemas import CandidateProfile, ContextBundle, JobData
from app.services.job_matcher import match_job
from app.services.job_normalizer import job_fingerprint, normalize_job
from app.services.semantic_matching import engine_key, similarity


def evaluate_job(
    db: Session, user_id: str, job: Job, profile: ProfileVersion, context: ContextVersion
) -> Evaluation:
    bundle = ContextBundle.model_validate(context.data)
    key = engine_key(bundle.rules.llm_consent)
    cached = db.scalar(
        select(Evaluation).where(
            Evaluation.user_id == user_id,
            Evaluation.job_id == job.id,
            Evaluation.profile_id == profile.id,
            Evaluation.context_id == context.id,
            Evaluation.engine_key == key,
        )
    )
    if cached:
        return cached
    candidate, vacancy = CandidateProfile.model_validate(profile.data), JobData.model_validate(job.data)
    semantic = similarity(db, user_id, candidate, vacancy, consent=bundle.rules.llm_consent)
    result = match_job(candidate, vacancy, bundle, semantic_similarity=semantic)
    row = Evaluation(
        user_id=user_id,
        job_id=job.id,
        profile_id=profile.id,
        context_id=context.id,
        score=result.score,
        eligible=result.eligible,
        data=result.model_dump(mode="json"),
        engine_key=key,
    )
    # A savepoint and unique constraint handle concurrent GET/rematch requests without duplicate cache rows.
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        row = db.execute(
            select(Evaluation).where(
                Evaluation.user_id == user_id,
                Evaluation.job_id == job.id,
                Evaluation.profile_id == profile.id,
                Evaluation.context_id == context.id,
                Evaluation.engine_key == key,
            )
        ).scalar_one()
    return row


def cached_source_jobs(db: Session, source: str, board: str | None) -> list[JobData]:
    key = f"{source}:{board or ''}"
    # The row lock serializes feed refreshes across workers, independent of user/query.
    if db.get(SourceCache, key) is None:
        try:
            with db.begin_nested():
                db.add(SourceCache(key=key, data=[]))
                db.flush()
        except IntegrityError:
            pass
    row = db.execute(
        select(SourceCache)
        .where(SourceCache.key == key)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    last = row.refreshed_at
    if last and last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    if last and datetime.now(UTC) - last < timedelta(hours=6):
        return [JobData.model_validate(item) for item in row.data]
    due = row.next_allowed_at
    if due and due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    if due and due > datetime.now(UTC):
        raise SourceError(
            "La fuente está en periodo de espera compartido.",
            transient=True,
            retry_after=max(1, int((due - datetime.now(UTC)).total_seconds())),
        )
    try:
        jobs = get_source(source).search("", board=board)
    except SourceError as exc:
        # Commit only source cooldown; the search failure is recorded by the caller.
        cooldown = max(exc.retry_after or 60, 21600 if source == "remotive" else 60)
        row.next_allowed_at = datetime.now(UTC) + timedelta(seconds=cooldown)
        db.commit()
        if exc.transient:
            exc.retry_after = cooldown
        raise
    row.data = [job.model_dump(mode="json") for job in jobs]
    row.refreshed_at = datetime.now(UTC)
    row.next_allowed_at = None
    db.flush()
    return jobs


def process_search(run_id: str) -> dict[str, Any]:
    with database.SessionLocal() as db:
        run = db.execute(
            select(SearchRun)
            .where(SearchRun.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if run is None:
            return {"status": "NOT_FOUND"}
        if run.status == "SUCCESS":
            return run.result
        due = run.next_attempt_at
        if due and due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        if due and due > datetime.now(UTC):
            return {"status": "RETRY_PENDING"}
        if run.status == "STARTED":
            started = run.started_at
            if started and started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            if started and datetime.now(UTC) - started < timedelta(minutes=5):
                return {"status": "STARTED"}
        owner = db.execute(
            select(User)
            .where(User.id == run.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if owner is None or (run.scheduled and not owner.automation_enabled):
            run.status = "SKIPPED"
            run.result = {"status": "SKIPPED", "reason": "automation_stopped"}
            db.commit()
            return run.result
        bundle = ContextBundle.model_validate(latest_context(db, run.user_id).data)
        if run.attempts >= bundle.rules.max_retries + 1:
            run.status = "FAILED"
            run.error = "Se agotó el máximo de intentos de búsqueda configurado."
            db.commit()
            return {"status": "FAILED"}
        run.status = "STARTED"
        run.started_at = datetime.now(UTC)
        run.attempts += 1
        run.next_attempt_at = None
        db.commit()
        try:
            jobs = cached_source_jobs(db, run.source, run.board)
            query = run.query.strip().casefold()
            jobs = [
                job
                for job in jobs
                if not query
                or query in f"{job.title} {job.company} {job.description} {' '.join(job.skills)}".casefold()
            ]
            # Serialize profile/context selection and per-user ingestion with edits and submissions.
            owner = db.execute(
                select(User)
                .where(User.id == run.user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).scalar_one()
            if run.scheduled and not owner.automation_enabled:
                run.status = "SKIPPED"
                run.result = {"status": "SKIPPED", "reason": "automation_stopped"}
                db.commit()
                return run.result
            profile = latest_profile(db, run.user_id)
            context = latest_context(db, run.user_id)
            inserted, duplicates = 0, 0
            for raw in jobs:
                job_data = normalize_job(raw)
                fingerprint = job_fingerprint(job_data)
                existing = db.scalar(
                    select(Job).where(
                        Job.user_id == run.user_id,
                        or_(
                            Job.fingerprint == fingerprint,
                            and_(Job.source == job_data.source, Job.external_id == job_data.external_id),
                        ),
                    )
                )
                if existing:
                    duplicates += 1
                    continue
                row = Job(
                    user_id=run.user_id,
                    fingerprint=fingerprint,
                    source=job_data.source,
                    external_id=job_data.external_id,
                    data=job_data.model_dump(mode="json"),
                )
                db.add(row)
                db.flush()
                if profile:
                    evaluate_job(db, run.user_id, row, profile, context)
                inserted += 1
            run.status = "SUCCESS"
            run.result = {"found": len(jobs), "inserted": inserted, "duplicates": duplicates}
            db.add(
                AuditEvent(
                    user_id=run.user_id,
                    kind="SEARCH_COMPLETED",
                    message=f"Búsqueda {run.source}: {inserted} nuevas, {duplicates} duplicadas.",
                )
            )
            db.commit()
            return run.result
        except Exception:
            # Provider exception text can contain URLs, authorization headers or personal data.
            db.rollback()
            failed = db.get(SearchRun, run_id)
            if failed:
                failed.status = "FAILED"
                failed.error = (
                    "No se pudo consultar la fuente. Revisa su disponibilidad y el identificador del portal."
                )
                db.add(AuditEvent(user_id=failed.user_id, kind="SEARCH_FAILED", message=failed.error))
                db.commit()
            raise
