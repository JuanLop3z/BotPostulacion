from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import DB, LocalUser, latest_context, latest_profile, lock_user
from app.core.config import get_settings
from app.integrations import list_sources
from app.models import Application, Job, SearchRun
from app.schemas.job_import import AssistedJobImport
from app.services.assisted_import import import_assisted_job, update_assisted_job
from app.services.search_pipeline import evaluate_job, process_search

router = APIRouter(tags=["jobs"])


@router.get("/sources")
def sources(user: LocalUser) -> list[dict[str, Any]]:
    return list_sources()


@router.post("/jobs/import", status_code=201)
def import_job(body: AssistedJobImport, response: Response, user: LocalUser, db: DB) -> dict[str, Any]:
    try:
        result = import_assisted_job(db, user, body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if result["duplicate"]:
        response.status_code = 200
    return result


@router.put("/jobs/{job_id}/import")
def complete_import(job_id: str, body: AssistedJobImport, user: LocalUser, db: DB) -> dict[str, Any]:
    try:
        return update_assisted_job(db, user, job_id, body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


class SearchRequest(BaseModel):
    source: Literal["remotive", "greenhouse", "demo"] = "greenhouse"
    query: str = Field(default="", max_length=200)
    board: str | None = Field(default=None, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")


def run_inline_safely(run_id: str) -> None:
    try:
        result = process_search(run_id)
        if result.get("status") not in {"FAILED", "STARTED", "SKIPPED", "NOT_FOUND"}:
            from app.agents.orchestrator import prepare_batch
            from app.database import session as database

            with database.SessionLocal() as db:
                run = db.get(SearchRun, run_id)
                user_id = run.user_id if run and run.status == "SUCCESS" else None
            if user_id:
                prepare_batch(user_id)
    except Exception:
        # The failure is already persisted and visible in /tasks and dashboard.
        pass


@router.post("/jobs/search", status_code=202)
def search(body: SearchRequest, background: BackgroundTasks, user: LocalUser, db: DB) -> dict[str, str]:
    lock_user(db, user)
    if body.source == "greenhouse" and not body.board:
        raise HTTPException(422, "Indica el token público del portal Greenhouse de la empresa")
    active = db.scalar(
        select(SearchRun).where(
            SearchRun.user_id == user.id, SearchRun.status.in_(["PENDING", "STARTED", "RETRY_PENDING"])
        )
    )
    if active:
        return {"task_id": active.id, "status": active.status}
    run = SearchRun(user_id=user.id, source=body.source, query=body.query, board=body.board)
    db.add(run)
    db.commit()
    if get_settings().inline_tasks:
        background.add_task(run_inline_safely, run.id)
    else:
        from app.workers.tasks import search_task

        try:
            search_task.delay(run.id)
        except Exception:
            run.status = "FAILED"
            run.error = "Worker no disponible. Verifica Redis y Celery."
            db.commit()
            raise HTTPException(503, run.error) from None
    return {"task_id": run.id, "status": "PENDING"}


@router.get("/tasks/{run_id}")
def task(run_id: str, user: LocalUser, db: DB) -> dict[str, Any]:
    row = db.get(SearchRun, run_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Tarea no encontrada")
    return {"id": row.id, "status": row.status, "result": row.result, "error": row.error}


@router.get("/jobs")
def jobs(
    user: LocalUser,
    db: DB,
    q: str = "",
    min_score: float = Query(0, ge=0, le=100),
    work_mode: str = "",
    company: str = "",
    location: str = "",
    technology: str = "",
    status: str = "",
    salary_min: float | None = None,
    published_after: str = "",
) -> list[dict[str, Any]]:
    profile = latest_profile(db, user.id)
    context = latest_context(db, user.id)
    rows = db.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(1000))
    applications = {
        app.job_id: app.state for app in db.scalars(select(Application).where(Application.user_id == user.id))
    }
    result = []
    for row in rows:
        data = row.data
        if q.casefold() not in f"{data['title']} {data['company']} {data.get('description', '')}".casefold():
            continue
        if (
            company.casefold() not in data["company"].casefold()
            or location.casefold() not in data.get("location", "").casefold()
        ):
            continue
        if work_mode and data.get("work_mode") != work_mode:
            continue
        if technology and technology.casefold() not in " ".join(data.get("skills", [])).casefold():
            continue
        if status and applications.get(row.id, "DISCOVERED") != status:
            continue
        # Amounts keep their original currency and period; no implicit currency conversion.
        if salary_min is not None and (data.get("salary_min") is None or data["salary_min"] < salary_min):
            continue
        if published_after and (data.get("published_at") or "") < published_after:
            continue
        evaluation = evaluate_job(db, user.id, row, profile, context) if profile else None
        if min_score and (evaluation is None or evaluation.score < min_score):
            continue
        result.append(
            {
                "id": row.id,
                **data,
                "match": evaluation.data if evaluation else None,
                "application_state": applications.get(row.id),
            }
        )
    db.commit()
    return sorted(result, key=lambda item: (item["match"] or {}).get("score", -1), reverse=True)


@router.post("/jobs/rematch")
def rematch(user: LocalUser, db: DB) -> dict[str, int]:
    lock_user(db, user)
    profile = latest_profile(db, user.id)
    if profile is None:
        raise HTTPException(409, "Primero carga y revisa un CV")
    context = latest_context(db, user.id)
    rows = list(db.scalars(select(Job).where(Job.user_id == user.id)))
    for row in rows:
        evaluate_job(db, user.id, row, profile, context)
    db.commit()
    return {"evaluated": len(rows)}
