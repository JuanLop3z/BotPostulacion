"""Persist provider Retry-After and global cooldowns across workers.

Revision ID: e039ed1aa421
Revises: a217c1d9e312
"""

import sqlalchemy as sa

from alembic import op

revision = "e039ed1aa421"
down_revision = "a217c1d9e312"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("search_runs", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("source_cache", sa.Column("next_allowed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("source_cache", "next_allowed_at")
    op.drop_column("search_runs", "next_attempt_at")
