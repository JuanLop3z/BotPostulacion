"""Scheduled search recovery and bounded attempts.

Revision ID: a217c1d9e312
Revises: 5dc96f558eb9
"""

import sqlalchemy as sa

from alembic import op

revision = "a217c1d9e312"
down_revision = "5dc96f558eb9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "search_runs", sa.Column("scheduled", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("search_runs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("search_runs", "attempts")
    op.drop_column("search_runs", "scheduled")
