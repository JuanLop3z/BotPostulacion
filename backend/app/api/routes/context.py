from typing import Any

from fastapi import APIRouter

from app.api.dependencies import DB, LocalUser, latest_context, lock_user
from app.core.config import get_settings
from app.models import AuditEvent, ContextVersion
from app.schemas import ContextBundle
from app.services.context_service import load_context

router = APIRouter(prefix="/context", tags=["context"])


@router.get("")
def get_context(user: LocalUser, db: DB) -> dict[str, Any]:
    lock_user(db, user)
    row = latest_context(db, user.id)
    db.commit()
    return {**row.data, "version": row.version}


@router.put("")
def update_context(body: ContextBundle, user: LocalUser, db: DB) -> dict[str, Any]:
    lock_user(db, user)
    old = latest_context(db, user.id)
    row = ContextVersion(user_id=user.id, version=old.version + 1, data=body.model_dump(mode="json"))
    db.add(row)
    db.add(
        AuditEvent(
            user_id=user.id, kind="CONTEXT_UPDATED", message="Contexto actualizado; reevalúa las vacantes."
        )
    )
    db.commit()
    return {**row.data, "version": row.version}


@router.post("/reload")
def reload_templates(user: LocalUser, db: DB) -> dict[str, Any]:
    return update_context(load_context(get_settings().context_dir), user, db)
