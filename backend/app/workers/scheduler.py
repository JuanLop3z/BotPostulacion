"""Run a single scheduler process. Stop and worker policies are rechecked under DB locks."""

from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import select

from app.api.dependencies import latest_context
from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models import LocalWorkspace, SearchRun, User
from app.schemas import ContextBundle
from app.workers.tasks import retention_task, search_task


def aware(stamp: datetime) -> datetime:
    return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp


def enqueue(run_id: str) -> None:
    try:
        search_task.delay(run_id)
    except Exception:
        with SessionLocal() as db:
            row = db.get(SearchRun, run_id)
            if row:
                row.status = "FAILED"
                row.error = "Worker no disponible. Verifica Redis y Celery."
                db.commit()


def recover_stalled_runs() -> int:
    recovered = []
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SearchRun)
                .where(SearchRun.status.in_(["STARTED", "PENDING", "RETRY_PENDING"]))
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            if row.next_attempt_at:
                if datetime.now(UTC) < aware(row.next_attempt_at) + timedelta(minutes=5):
                    continue
            elapsed = datetime.now(UTC) - aware(row.started_at or row.created_at)
            if elapsed < timedelta(minutes=5 if row.status == "STARTED" else 10):
                continue
            owner = db.get(User, row.user_id)
            if owner is None or (row.scheduled and not owner.automation_enabled):
                row.status = "SKIPPED"
                continue
            rules = ContextBundle.model_validate(latest_context(db, row.user_id).data).rules
            if row.attempts >= rules.max_retries + 1:
                row.status = "FAILED"
                row.error = "Se agotó el máximo de intentos de búsqueda configurado."
                continue
            row.status = "RETRY_PENDING"
            row.started_at = datetime.now(UTC)
            row.next_attempt_at = None
            recovered.append(row.id)
        db.commit()
    for run_id in recovered:
        enqueue(run_id)
    return len(recovered)


def schedule_searches() -> None:
    recover_stalled_runs()
    with SessionLocal() as db:
        user_ids = list(
            db.scalars(
                select(User.id)
                .join(LocalWorkspace, LocalWorkspace.user_id == User.id)
                .where(User.automation_enabled.is_(True))
            )
        )
    for user_id in user_ids:
        queued = []
        with SessionLocal() as db:
            user = db.scalar(
                select(User)
                .where(User.id == user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if user is None or not user.automation_enabled:
                continue
            bundle = ContextBundle.model_validate(latest_context(db, user.id).data)
            for source in bundle.rules.permitted_sources:
                if source not in {"remotive", "demo"}:
                    continue
                last = db.scalar(
                    select(SearchRun)
                    .where(SearchRun.user_id == user.id, SearchRun.source == source)
                    .order_by(SearchRun.created_at.desc())
                    .limit(1)
                )
                if last and (
                    last.status in {"PENDING", "STARTED", "RETRY_PENDING"}
                    or datetime.now(UTC) - aware(last.created_at)
                    < timedelta(hours=bundle.rules.search_interval_hours)
                ):
                    continue
                run = SearchRun(user_id=user.id, source=source, query="", scheduled=True)
                db.add(run)
                db.flush()
                queued.append(run.id)
            db.commit()
        for run_id in queued:
            enqueue(run_id)


def main() -> None:
    scheduler = BlockingScheduler(timezone=get_settings().timezone)
    scheduler.add_job(schedule_searches, "interval", minutes=5, max_instances=1, coalesce=True)
    scheduler.add_job(retention_task.delay, "cron", hour=3, minute=0)
    scheduler.start()


if __name__ == "__main__":
    main()
