"""Explicit workflow composition; job descriptions never enter a tool execution loop."""

from sqlalchemy import select

from app.api.dependencies import latest_context
from app.database import session as database
from app.models import Application, Job, User
from app.schemas import ContextBundle
from app.services.application_manager import prepare, submit
from app.services.search_pipeline import process_search


def run_batch(run_id: str, user_id: str) -> dict[str, int]:
    result = process_search(run_id)
    if result.get("status") in {"FAILED", "STARTED", "SKIPPED", "NOT_FOUND"}:
        return {"prepared": 0, "submitted": 0}
    return prepare_batch(user_id)


def prepare_batch(user_id: str) -> dict[str, int]:
    prepared = submitted = 0
    with database.SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.automation_enabled:
            return {"prepared": 0, "submitted": 0}
        rules = ContextBundle.model_validate(latest_context(db, user_id).data).rules
        if rules.mode == "manual":
            return {"prepared": 0, "submitted": 0}
        jobs = list(db.scalars(select(Job).where(Job.user_id == user_id)))
        for job in jobs:
            existing = db.scalar(
                select(Application).where(Application.job_id == job.id, Application.user_id == user_id)
            )
            if existing:
                continue
            application = prepare(db, user, job.id)
            db.commit()
            prepared += 1
            if (
                rules.mode == "automatic"
                and rules.automatic_enabled
                and not rules.requires_approval
                and job.source == "demo"
                and application.state == "PENDING_APPROVAL"
            ):
                from fastapi import HTTPException

                try:
                    submit(db, user, application.id, automatic=True)
                    db.commit()
                    submitted += 1
                except HTTPException:
                    db.rollback()
    return {"prepared": prepared, "submitted": submitted}
