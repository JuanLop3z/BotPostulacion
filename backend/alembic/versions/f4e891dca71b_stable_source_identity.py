"""Prevent duplicate applications after a source edits a vacancy title or location.

Revision ID: f4e891dca71b
Revises: e039ed1aa421
"""

from alembic import op

revision = "f4e891dca71b"
down_revision = "e039ed1aa421"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch mode supports SQLite as well as PostgreSQL.
    with op.batch_alter_table("jobs") as batch:
        batch.create_unique_constraint("uq_jobs_user_source_external", ["user_id", "source", "external_id"])


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint("uq_jobs_user_source_external", type_="unique")
