"""Persist the single local workspace without changing existing profiles or documents.

Revision ID: 7b1d06e4a382
Revises: f4e891dca71b
"""

import sqlalchemy as sa

from alembic import op

revision = "7b1d06e4a382"
down_revision = "f4e891dca71b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "local_workspace",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_local_workspace_singleton"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("local_workspace")
