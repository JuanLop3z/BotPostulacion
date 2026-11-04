from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import ContextVersion, ProfileVersion, User
from app.schemas import ContextBundle
from app.services.context_service import load_context
from app.services.workspace import get_local_user

DB = Annotated[Session, Depends(get_db)]


def local_user(db: DB) -> User:
    return get_local_user(db)


LocalUser = Annotated[User, Depends(local_user)]


def lock_user(db: Session, user: User) -> User:
    from sqlalchemy import select

    return db.execute(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    ).scalar_one()


def latest_profile(db: Session, user_id: str) -> ProfileVersion | None:
    from sqlalchemy import select

    return db.scalar(
        select(ProfileVersion)
        .where(ProfileVersion.user_id == user_id)
        .order_by(ProfileVersion.version.desc())
        .limit(1)
    )


def latest_context(db: Session, user_id: str) -> ContextVersion:
    from sqlalchemy import select

    from app.core.config import get_settings

    result = db.scalar(
        select(ContextVersion)
        .where(ContextVersion.user_id == user_id)
        .order_by(ContextVersion.version.desc())
        .limit(1)
    )
    if result is None:
        context: ContextBundle = load_context(get_settings().context_dir)
        result = ContextVersion(user_id=user_id, version=1, data=context.model_dump(mode="json"))
        from sqlalchemy.exc import IntegrityError

        try:
            with db.begin_nested():
                db.add(result)
                db.flush()
        except IntegrityError:
            result = db.execute(
                select(ContextVersion)
                .where(ContextVersion.user_id == user_id)
                .order_by(ContextVersion.version.desc())
                .limit(1)
            ).scalar_one()
    return result
