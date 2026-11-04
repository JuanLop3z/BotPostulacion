import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def identifier() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LocalWorkspace(Base):
    __tablename__ = "local_workspace"
    __table_args__ = (CheckConstraint("id = 1", name="ck_local_workspace_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)


class Owned:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CVDocument(Owned, Base):
    __tablename__ = "cv_documents"
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)


class ProfileVersion(Owned, Base):
    __tablename__ = "profile_versions"
    __table_args__ = (UniqueConstraint("user_id", "version"),)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)


class ContextVersion(Owned, Base):
    __tablename__ = "context_versions"
    __table_args__ = (UniqueConstraint("user_id", "version"),)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class Job(Owned, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "fingerprint"),
        UniqueConstraint("user_id", "source", "external_id"),
    )
    fingerprint: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(40), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class Evaluation(Owned, Base):
    __tablename__ = "evaluations"
    __table_args__ = (UniqueConstraint("user_id", "job_id", "profile_id", "context_id", "engine_key"),)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profile_versions.id", ondelete="CASCADE"))
    context_id: Mapped[str] = mapped_column(ForeignKey("context_versions.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float)
    eligible: Mapped[bool] = mapped_column(Boolean)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    engine_key: Mapped[str] = mapped_column(String(64), default="rules-v1")


class EmbeddingCache(Owned, Base):
    __tablename__ = "embedding_cache"
    __table_args__ = (UniqueConstraint("user_id", "cache_key"),)
    cache_key: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(200))
    vector: Mapped[Any] = mapped_column(Vector().with_variant(JSON(), "sqlite"))


class Application(Owned, Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_id"),)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profile_versions.id"))
    context_id: Mapped[str] = mapped_column(ForeignKey("context_versions.id"))
    state: Mapped[str] = mapped_column(String(40), default="DISCOVERED", index=True)
    packet: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    result_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditEvent(Owned, Base):
    __tablename__ = "audit_events"
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SearchRun(Owned, Base):
    __tablename__ = "search_runs"
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    source: Mapped[str] = mapped_column(String(40))
    query: Mapped[str] = mapped_column(String(200), default="")
    board: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SourceCache(Base):
    __tablename__ = "source_cache"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_allowed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
