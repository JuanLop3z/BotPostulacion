import csv
import io
from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, text

from app.api.dependencies import DB, LocalUser, latest_context, latest_profile, lock_user
from app.models import Application, AuditEvent, Job
from app.schemas import ContextBundle
from app.services.search_pipeline import evaluate_job

router = APIRouter(tags=["dashboard", "automation"])


@router.get("/dashboard")
def dashboard(user: LocalUser, db: DB) -> dict[str, Any]:
    profile = latest_profile(db, user.id)
    context = latest_context(db, user.id)
    jobs = list(db.scalars(select(Job).where(Job.user_id == user.id)))
    evaluations = [evaluate_job(db, user.id, job, profile, context) for job in jobs] if profile else []
    apps = list(db.scalars(select(Application).where(Application.user_id == user.id)))
    sources = {job.id: job.source for job in jobs}
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.user_id == user.id)
            .order_by(AuditEvent.created_at.desc())
            .limit(15)
        )
    )
    gaps: Counter[str] = Counter()
    for evaluation in evaluations:
        gaps.update(evaluation.data.get("gaps", []))
    db.commit()
    return {
        "jobs": len(jobs),
        "eligible_jobs": sum(row.eligible for row in evaluations),
        "applications": len(apps),
        "pending_approval": sum(row.state == "PENDING_APPROVAL" for row in apps),
        "submitted": sum(row.submitted_at is not None for row in apps),
        "confirmed": sum(row.state == "CONFIRMED" for row in apps),
        "demo_submitted": sum(
            row.submitted_at is not None and sources.get(row.job_id) == "demo" for row in apps
        ),
        "real_submitted": sum(
            row.submitted_at is not None and sources.get(row.job_id) != "demo" for row in apps
        ),
        "platform_confirmed": sum(
            row.state == "CONFIRMED"
            and sources.get(row.job_id) != "demo"
            and not row.evidence.get("reported_by_user")
            for row in apps
        ),
        "user_confirmed": sum(
            row.state == "CONFIRMED" and bool(row.evidence.get("reported_by_user")) for row in apps
        ),
        "average_score": round(sum(row.score for row in evaluations) / len(evaluations), 1)
        if evaluations
        else 0,
        "ai_cost_usd": None,
        "ai_cost_note": "Sin medición del proveedor. La extracción y matching locales no consumen créditos.",
        "automation_enabled": user.automation_enabled,
        "recent_events": [
            {"id": row.id, "kind": row.kind, "message": row.message, "created_at": row.created_at}
            for row in events
        ],
        "skill_gaps": [{"skill": skill, "count": count} for skill, count in gaps.most_common(10)],
    }


@router.post("/automation/stop")
def stop(user: LocalUser, db: DB) -> dict[str, Any]:
    user = lock_user(db, user)
    user.automation_enabled = False
    db.add(
        AuditEvent(
            user_id=user.id,
            kind="AUTOMATION_STOPPED",
            message="Parada activa: se bloquean nuevos envíos y búsquedas programadas.",
        )
    )
    db.commit()
    return {"automation_enabled": False}


@router.post("/automation/start")
def start(user: LocalUser, db: DB) -> dict[str, Any]:
    user = lock_user(db, user)
    profile = latest_profile(db, user.id)
    if profile is None or not profile.reviewed:
        raise HTTPException(409, "Revisa el perfil antes de habilitar la automatización")
    rules = ContextBundle.model_validate(latest_context(db, user.id).data).rules
    if rules.mode == "automatic" and not rules.automatic_enabled:
        raise HTTPException(409, "Activa expresamente el modo automático en las reglas")
    user.automation_enabled = True
    db.add(
        AuditEvent(
            user_id=user.id,
            kind="AUTOMATION_STARTED",
            message="Automatización habilitada conforme a las reglas actuales.",
        )
    )
    db.commit()
    return {"automation_enabled": True}


def csv_safe(value: str) -> str:
    # Prevent spreadsheet formulas in job descriptions supplied by third parties.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


@router.get("/reports/applications.csv")
def report(user: LocalUser, db: DB) -> Response:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["id", "cargo", "empresa", "fuente", "estado", "referencia", "creada", "simulación"])
    for app in db.scalars(select(Application).where(Application.user_id == user.id)):
        job = db.get(Job, app.job_id)
        writer.writerow(
            [
                app.id,
                csv_safe(job.data["title"] if job else ""),
                csv_safe(job.data["company"] if job else ""),
                job.source if job else "",
                app.state,
                csv_safe(app.result_reference or ""),
                app.created_at.isoformat(),
                bool(app.evidence.get("simulation")),
            ]
        )
    return Response(
        buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="autojob-postulaciones.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/health/ready")
def ready(db: DB) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
