"""Committed records from another client fixture must never leak into a test."""

import pytest
from sqlalchemy import func, select, text

from app.database import session as database
from app.models import SourceCache, User


@pytest.mark.parametrize("attempt", [1, 2])
def test_client_fixture_isolates_committed_records(client, attempt: int) -> None:
    with database.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(SourceCache)) == 0
        if db.get_bind().dialect.name == "postgresql":
            # Migration tables in public must not satisfy the test schema's DDL.
            table_schema = db.scalar(
                text(
                    "SELECT n.nspname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.oid = to_regclass('users')"
                )
            )
            assert table_schema.startswith("test_")
        db.add(
            User(
                email="fixture-isolation@example.test",
                full_name=f"Fixture {attempt}",
                password_hash="disabled",
            )
        )
        db.add(SourceCache(key="fixture-isolation", data=[]))
        db.commit()
