from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.dependencies import DB, LocalUser, lock_user
from app.models import Application
from app.services import application_manager as manager

router = APIRouter(prefix="/applications", tags=["applications"])


class PrepareRequest(BaseModel):
    job_id: str


@router.get("")
def applications(user: LocalUser, db: DB) -> list[dict[str, Any]]:
    return [
        manager.serialize_application(db, row)
        for row in db.scalars(
            select(Application).where(Application.user_id == user.id).order_by(Application.created_at.desc())
        )
    ]


@router.post("", status_code=201)
def prepare(body: PrepareRequest, user: LocalUser, db: DB) -> dict[str, Any]:
    row = manager.prepare(db, user, body.job_id)
    db.commit()
    return manager.serialize_application(db, row)


@router.post("/{application_id}/approve")
def approve(application_id: str, user: LocalUser, db: DB) -> dict[str, Any]:
    row = manager.approve(db, user, application_id)
    db.commit()
    return manager.serialize_application(db, row)


@router.post("/{application_id}/regenerate")
def regenerate(application_id: str, user: LocalUser, db: DB) -> dict[str, Any]:
    lock_user(db, user)
    row = manager.owned_application(db, user, application_id)
    if row.state in {"SUBMITTED", "CONFIRMED", "WITHDRAWN", "SKIPPED"}:
        raise HTTPException(409, "Esta candidatura ya es definitiva")
    if row.state in {"PENDING_APPROVAL", "PREPARED"}:
        manager.transition(
            db, row, "NEEDS_INFORMATION", "Se solicitó regenerar la candidatura con el perfil actual."
        )
    row = manager.prepare(db, user, row.job_id)
    db.commit()
    return manager.serialize_application(db, row)


@router.post("/{application_id}/reject")
def reject(application_id: str, user: LocalUser, db: DB) -> dict[str, Any]:
    lock_user(db, user)
    row = manager.owned_application(db, user, application_id)
    if row.state not in {"SKIPPED", "WITHDRAWN"}:
        target = "WITHDRAWN" if row.state in {"SUBMITTED", "CONFIRMED"} else "SKIPPED"
        manager.transition(db, row, target, "Estado actualizado por decisión del usuario; registro local.")
    db.commit()
    return manager.serialize_application(db, row)


@router.post("/{application_id}/submit")
def submit(application_id: str, user: LocalUser, db: DB) -> dict[str, Any]:
    row = manager.submit(db, user, application_id)
    db.commit()
    return manager.serialize_application(db, row)


class ManualConfirmation(BaseModel):
    confirmed: bool = False


@router.post("/{application_id}/manual-confirm")
def manual_confirm(application_id: str, body: ManualConfirmation, user: LocalUser, db: DB) -> dict[str, Any]:
    from datetime import UTC, datetime

    lock_user(db, user)
    row = manager.owned_application(db, user, application_id)
    if row.state in {"CONFIRMED", "WITHDRAWN"}:
        return manager.serialize_application(db, row)
    if row.state not in {"PREPARED", "SUBMITTED"} or not row.approved:
        raise HTTPException(409, "Aprueba primero la candidatura preparada")
    if row.state == "PREPARED":
        manager.validate_snapshot(db, user, row)
        row.submitted_at = datetime.now(UTC)
        row.evidence = {"reported_by_user": True, "platform_verified": False}
        manager.transition(
            db, row, "SUBMITTED", "El usuario registró un envío realizado en el portal externo."
        )
    if body.confirmed:
        manager.transition(db, row, "CONFIRMED", "El usuario declaró haber recibido confirmación del portal.")
    db.commit()
    return manager.serialize_application(db, row)
