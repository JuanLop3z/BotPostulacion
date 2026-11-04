from typing import Any

from fastapi import APIRouter
from sqlalchemy import delete, select

from app.api.dependencies import DB, LocalUser, latest_profile, lock_user
from app.core.config import get_settings
from app.models import CVDocument, LocalWorkspace, User
from app.services.workspace import new_local_user

router = APIRouter(prefix="/workspace", tags=["personal workspace"])


@router.get("")
def workspace(user: LocalUser, db: DB) -> dict[str, Any]:
    profile = latest_profile(db, user.id)
    name = profile.data.get("full_name", "") if profile else user.full_name
    email = profile.data.get("email", "") if profile else user.email
    return {
        "id": user.id,
        "full_name": name,
        "email": "" if email.endswith("@autojob.invalid") else email,
        "mode": "personal",
    }


@router.delete("", status_code=204)
def reset_workspace(user: LocalUser, db: DB) -> None:
    lock_user(db, user)
    files = list(db.scalars(select(CVDocument.storage_key).where(CVDocument.user_id == user.id)))
    db.execute(delete(User).where(User.id == user.id))
    fresh = new_local_user()
    db.add(fresh)
    db.flush()
    db.add(LocalWorkspace(id=1, user_id=fresh.id))
    db.commit()
    for key in files:
        (get_settings().storage_dir / "cv" / key).unlink(missing_ok=True)
