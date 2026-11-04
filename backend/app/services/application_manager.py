from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import latest_context, latest_profile, lock_user
from app.automation.submission_guard import SubmissionGuard
from app.core.config import get_settings
from app.integrations import SourceError, get_source
from app.models import Application, AuditEvent, Job, User
from app.schemas import CandidateProfile, ContextBundle, JobData, MatchResult
from app.services.application_builder import build_application
from app.services.search_pipeline import evaluate_job

TRANSITIONS: dict[str, set[str]] = {
    "DISCOVERED": {"ANALYZED", "SKIPPED"},
    "ANALYZED": {"ELIGIBLE", "REJECTED_BY_RULES", "NEEDS_INFORMATION"},
    "ELIGIBLE": {"PREPARED"},
    "PREPARED": {"PENDING_APPROVAL", "SUBMITTED", "SKIPPED", "NEEDS_INFORMATION"},
    "PENDING_APPROVAL": {"PREPARED", "SKIPPED", "NEEDS_INFORMATION"},
    "NEEDS_INFORMATION": {"ANALYZED", "SKIPPED"},
    "REJECTED_BY_RULES": {"ANALYZED", "SKIPPED"},
    "FAILED": {"RETRY_PENDING", "SKIPPED"},
    "RETRY_PENDING": {"PREPARED", "FAILED", "NEEDS_INFORMATION"},
    "SUBMITTED": {"CONFIRMED", "WITHDRAWN"},
    "CONFIRMED": {"WITHDRAWN"},
    "SKIPPED": set(),
    "WITHDRAWN": set(),
}


def transition(db: Session, app: Application, state: str, message: str) -> None:
    if state not in TRANSITIONS.get(app.state, set()):
        raise HTTPException(409, f"Transición no permitida: {app.state} → {state}")
    old = app.state
    app.state = state
    app.updated_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            user_id=app.user_id,
            application_id=app.id,
            kind=state,
            message=message,
            details={"from": old, "to": state},
        )
    )


def owned_application(db: Session, user: User, application_id: str) -> Application:
    app = db.scalar(
        select(Application)
        .where(Application.id == application_id, Application.user_id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if app is None:
        raise HTTPException(404, "Candidatura no encontrada")
    return app


def serialize_application(db: Session, app: Application) -> dict[str, Any]:
    job = db.get(Job, app.job_id)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.application_id == app.id).order_by(AuditEvent.created_at)
        )
    )
    return {
        "id": app.id,
        "job_id": app.job_id,
        "job_title": job.data["title"] if job else "",
        "company": job.data["company"] if job else "",
        "source": job.source if job else "",
        "url": job.data["url"] if job else "",
        "state": app.state,
        "packet": app.packet,
        "approved": app.approved,
        "created_at": app.created_at,
        "updated_at": app.updated_at,
        "result_reference": app.result_reference,
        "evidence": app.evidence,
        "attempts": app.attempts,
        "events": [
            {"id": event.id, "kind": event.kind, "message": event.message, "created_at": event.created_at}
            for event in events
        ],
    }


def prepare(db: Session, user: User, job_id: str) -> Application:
    lock_user(db, user)
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    if job is None:
        raise HTTPException(404, "Vacante no encontrada")
    profile = latest_profile(db, user.id)
    if profile is None:
        raise HTTPException(409, "Carga tu CV antes de preparar candidaturas")
    context = latest_context(db, user.id)
    app = db.scalar(select(Application).where(Application.user_id == user.id, Application.job_id == job_id))
    if app:
        if app.state not in {"NEEDS_INFORMATION", "REJECTED_BY_RULES"}:
            return app
        app.profile_id, app.context_id = profile.id, context.id
        app.approved = False
    else:
        app = Application(
            user_id=user.id,
            job_id=job_id,
            profile_id=profile.id,
            context_id=context.id,
            state="DISCOVERED",
            packet={},
        )
        db.add(app)
        db.flush()
    evaluation = evaluate_job(db, user.id, job, profile, context)
    match = MatchResult.model_validate(evaluation.data)
    transition(db, app, "ANALYZED", "Compatibilidad y requisitos evaluados.")
    if not match.eligible:
        state = "NEEDS_INFORMATION" if match.requires_human_review else "REJECTED_BY_RULES"
        transition(
            db,
            app,
            state,
            "Revisión de condiciones pendiente."
            if match.requires_human_review
            else "Hay requisitos excluyentes pendientes o incumplidos.",
        )
        app.packet = {
            "blockers": match.blockers,
            "pending_questions": list(dict.fromkeys(match.gaps + match.blockers)),
        }
        return app
    transition(db, app, "ELIGIBLE", "Vacante elegible conforme al perfil revisado.")
    packet = build_application(
        CandidateProfile.model_validate(profile.data), JobData.model_validate(job.data), match
    )
    app.packet = packet
    transition(db, app, "PREPARED", "Candidatura preparada con hechos verificables.")
    if packet.get("pending_questions") or packet.get("unverified_fields"):
        transition(db, app, "NEEDS_INFORMATION", "Completa los datos o respuestas pendientes.")
    else:
        transition(db, app, "PENDING_APPROVAL", "Candidatura lista para revisión individual.")
    return app


def approve(db: Session, user: User, application_id: str) -> Application:
    lock_user(db, user)
    app = owned_application(db, user, application_id)
    if app.approved and app.state == "PREPARED":
        return app
    if app.state != "PENDING_APPROVAL":
        raise HTTPException(409, "La candidatura no está pendiente de aprobación")
    validate_snapshot(db, user, app)
    app.approved = True
    transition(db, app, "PREPARED", "Aprobación individual registrada.")
    return app


def validate_snapshot(db: Session, user: User, app: Application) -> None:
    profile = latest_profile(db, user.id)
    context = latest_context(db, user.id)
    if profile is None or profile.id != app.profile_id or context.id != app.context_id:
        raise HTTPException(
            409, "El perfil o contexto cambió. Regenera la candidatura antes de aprobar o enviar."
        )


def quota_counts(db: Session, user_id: str) -> tuple[int, int]:
    local = datetime.now(ZoneInfo(get_settings().timezone))
    day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    week = day - timedelta(days=day.weekday())

    def count(since: datetime) -> int:
        return (
            db.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.user_id == user_id, Application.submitted_at >= since.astimezone(UTC))
            )
            or 0
        )

    return count(day), count(week)


def submit(db: Session, user: User, application_id: str, *, automatic: bool = False) -> Application:
    user = lock_user(db, user)
    app = owned_application(db, user, application_id)
    if app.state in {"SUBMITTED", "CONFIRMED", "WITHDRAWN"}:
        return app  # Idempotent even if a client loses the response.
    validate_snapshot(db, user, app)
    if app.state not in {"PREPARED", "PENDING_APPROVAL"}:
        raise HTTPException(409, "La candidatura no está lista para envío")
    profile = latest_profile(db, user.id)
    context = latest_context(db, user.id)
    job = db.get(Job, app.job_id)
    assert profile is not None and job is not None
    rules = ContextBundle.model_validate(context.data).rules
    evaluation = evaluate_job(db, user.id, job, profile, context)
    adapter = get_source(job.source)
    daily, weekly = quota_counts(db, user.id)
    guard = SubmissionGuard.check(
        rules=rules,
        profile=CandidateProfile.model_validate(profile.data),
        job=JobData.model_validate(job.data),
        match=MatchResult.model_validate(evaluation.data),
        adapter=adapter,
        approved=app.approved,
        daily_count=daily,
        weekly_count=weekly,
        stopped=not user.automation_enabled,
        packet=app.packet,
        automatic=automatic,
    )
    if not guard.allowed:
        raise HTTPException(409, " ".join(guard.blockers))
    if automatic and app.state == "PENDING_APPROVAL":
        transition(db, app, "PREPARED", "Envío automático habilitado expresamente por reglas.")
    app.attempts += 1
    try:
        result = adapter.submit(app.id, app.packet)
    except SourceError as exc:
        # No automatic retry after a possibly successful external POST; future adapters must reconcile evidence.
        transition(
            db, app, "NEEDS_INFORMATION", "El proveedor requiere revisión del resultado antes de reintentar."
        )
        db.commit()
        raise HTTPException(409 if exc.requires_human else 502, "El envío requiere revisión humana") from None
    if not result.submitted or not result.reference or not result.evidence:
        transition(
            db, app, "NEEDS_INFORMATION", "Respuesta del proveedor incompleta; revisa antes de reintentar."
        )
        db.commit()
        raise HTTPException(502, "El proveedor no devolvió evidencia válida de envío")
    app.result_reference = result.reference
    app.evidence = result.evidence
    app.submitted_at = datetime.now(UTC)
    transition(db, app, "SUBMITTED", "Formulario enviado; evidencia registrada.")
    if result.confirmed:
        transition(db, app, "CONFIRMED", "Recepción confirmada por el proveedor de pruebas local.")
    return app
