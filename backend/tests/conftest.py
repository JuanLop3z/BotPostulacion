import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.database import session as database
from app.database.session import Base, get_db
from app.main import app
from app.models import User


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    postgres_url = os.environ.get("TEST_DATABASE_URL")
    admin = None
    schema = "test_" + uuid.uuid4().hex
    if postgres_url:
        admin = create_engine(postgres_url)
        with admin.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(postgres_url, connect_args={"options": f"-csearch_path={schema},public"})
    else:
        engine = create_engine(
            f"sqlite:///{tmp_path / 'tests.db'}", connect_args={"check_same_thread": False}
        )

    @event.listens_for(engine, "connect")
    def enable_fk(connection, _record):
        if not postgres_url:
            connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(get_settings(), "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(get_settings(), "inline_tasks", True)
    monkeypatch.setattr(get_settings(), "llm_endpoint", "")
    monkeypatch.setattr(get_settings(), "local_user_id", "")

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
    if admin:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def headers(client) -> dict[str, str]:
    """Existing endpoint fixtures deliberately run with no authentication headers."""
    response = client.get("/api/v1/workspace")
    assert response.status_code == 200, response.text
    return {}


@pytest.fixture
def legacy_owner(client) -> str:
    """An old storage owner, accessible only through direct DB fixtures, never through login."""
    with database.SessionLocal() as db:
        user = User(email="legacy@example.test", full_name="Legacy", password_hash="disabled")
        db.add(user)
        db.commit()
        return user.id


@pytest.fixture
def ready_profile(client, headers):
    cv = """Nombre: Ana Prueba
Email: candidate@example.test
Cargo: Senior Backend Developer
Ubicación: Colombia
Experiencia: 6 años de experiencia
Habilidades: Python, FastAPI, PostgreSQL, Docker, SQL, Git
Idiomas: Inglés C1, Español nativo
"""
    response = client.post(
        "/api/v1/cv", headers=headers, files={"file": ("resume.txt", cv.encode(), "text/plain")}
    )
    assert response.status_code == 201, response.text
    reviewed = client.post("/api/v1/profile/review", headers=headers)
    assert reviewed.status_code == 200, reviewed.text
    context = client.get("/api/v1/context", headers=headers).json()
    context.pop("version", None)
    context["rules"]["minimum_score"] = 0
    context["preferences"]["countries"] = []
    context["preferences"]["work_modes"] = ["remote", "hybrid", "onsite", "unknown"]
    assert client.put("/api/v1/context", headers=headers, json=context).status_code == 200
    return reviewed.json()


@pytest.fixture
def demo_jobs(client, headers, ready_profile):
    response = client.post("/api/v1/jobs/search", headers=headers, json={"source": "demo"})
    assert response.status_code == 202, response.text
    task = client.get("/api/v1/tasks/" + response.json()["task_id"], headers=headers)
    assert task.json()["status"] == "SUCCESS", task.text
    result = client.get("/api/v1/jobs", headers=headers)
    assert result.status_code == 200, result.text
    return result.json()
