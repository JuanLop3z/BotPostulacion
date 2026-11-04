"""A persistent owner for this personal installation; no login or browser token."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import LocalWorkspace, User


def new_local_user() -> User:
    from uuid import uuid4

    owner_id = str(uuid4())
    return User(id=owner_id, email=f"{owner_id}@autojob.invalid", full_name="", password_hash="disabled")


def get_local_user(db: Session) -> User:
    workspace = db.get(LocalWorkspace, 1)
    if workspace:
        return db.execute(select(User).where(User.id == workspace.user_id)).scalar_one()
    preferred_id = get_settings().local_user_id
    user = (
        db.get(User, preferred_id)
        if preferred_id
        else db.scalar(select(User).order_by(User.created_at, User.id).limit(1))
    )
    if preferred_id and user is None:
        raise HTTPException(409, "LOCAL_USER_ID no corresponde a un perfil existente")
    try:
        with db.begin_nested():
            if user is None:
                # Internal storage identity only; never used as candidate/contact information.
                user = new_local_user()
                db.add(user)
                db.flush()
            db.add(LocalWorkspace(id=1, user_id=user.id))
            db.flush()
    except IntegrityError:
        workspace = db.execute(select(LocalWorkspace).where(LocalWorkspace.id == 1)).scalar_one()
        user = db.execute(select(User).where(User.id == workspace.user_id)).scalar_one()
    db.commit()
    return user
