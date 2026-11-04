from datetime import UTC, datetime, timedelta

from celery import Celery
from sqlalchemy import select

from app.api.dependencies import latest_context
from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models import AuditEvent, CVDocument, SearchRun
from app.schemas import ContextBundle
from app.services.search_pipeline import process_search

settings = get_settings()
celery_app = Celery("autojob", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.timezone,
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_time_limit=180,
)


@celery_app.task(bind=True, max_retries=5, name="autojob.search")
def search_task(self, run_id: str):  # type: ignore[no-untyped-def]
    from app.integrations import SourceError

    try:
        result = process_search(run_id)
        from app.agents.orchestrator import prepare_batch

        with SessionLocal() as db:
            run = db.get(SearchRun, run_id)
            user_id = run.user_id if run and run.status == "SUCCESS" else None
        if user_id:
            result = {**result, **prepare_batch(user_id)}
        return result
    except SourceError as exc:
        with SessionLocal() as db:
            run = db.get(SearchRun, run_id)
            limit = (
                ContextBundle.model_validate(latest_context(db, run.user_id).data).rules.max_retries
                if run
                else 0
            )
            if exc.transient and not exc.requires_human and self.request.retries < limit:
                delay = max(exc.retry_after or 0, 60 * 2**self.request.retries)
                if run:
                    run.status = "RETRY_PENDING"
                    run.error = "Fallo transitorio del proveedor. Reintento limitado en espera."
                    run.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
                    db.commit()
                raise self.retry(countdown=delay) from None
        raise


@celery_app.task(name="autojob.retention")
def retention_task() -> dict[str, int]:
    cutoff = datetime.now(UTC) - timedelta(days=settings.retention_days)
    with SessionLocal() as db:
        docs = list(db.scalars(select(CVDocument).where(CVDocument.created_at < cutoff)))
        for doc in docs:
            (settings.storage_dir / "cv" / doc.storage_key).unlink(missing_ok=True)
            db.delete(doc)
        for event in db.scalars(select(AuditEvent).where(AuditEvent.created_at < cutoff)):
            db.delete(event)
        db.commit()
        return {"documents_removed": len(docs)}
