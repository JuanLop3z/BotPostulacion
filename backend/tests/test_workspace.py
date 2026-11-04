import pytest
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.database import session as database
from app.models import LocalWorkspace, ProfileVersion, User
from app.schemas import CandidateProfile

PREFIX = "/api/v1"


@pytest.mark.parametrize("configured", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_legacy_cors_setting_accepts_both_local_browser_addresses(configured):
    settings = Settings(_env_file=None, cors_origins=f" {configured}/ ")
    assert set(settings.cors_origins.split(",")) == {"http://localhost:3000", "http://127.0.0.1:3000"}


def test_local_cors_alias_keeps_the_port_and_remote_origin_restrictions():
    settings = Settings(_env_file=None, cors_origins="http://localhost:3001,https://allowed.example")
    assert set(settings.cors_origins.split(",")) == {
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://allowed.example",
    }


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_local_browser_get_and_json_preflight_have_cors_headers(client, origin):
    response = client.get(PREFIX + "/workspace", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    preflight = client.options(
        PREFIX + "/profile",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin


def test_existing_profile_and_owner_are_adopted_without_creating_an_account(client, legacy_owner):
    data = CandidateProfile(full_name="Perfil existente", email="existing@example.test").model_dump(
        mode="json"
    )
    with database.SessionLocal() as db:
        db.add(ProfileVersion(user_id=legacy_owner, version=7, data=data, reviewed=False))
        db.commit()
    workspace = client.get(PREFIX + "/workspace").json()
    assert workspace["id"] == legacy_owner
    assert workspace["full_name"] == "Perfil existente"
    assert client.get(PREFIX + "/profile").json()["version"] == 7
    assert client.get(PREFIX + "/workspace").json() == workspace
    with database.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.get(LocalWorkspace, 1).user_id == legacy_owner


def test_manual_profile_entry_without_cv_or_credentials(client):
    assert client.get(PREFIX + "/profile").json() is None
    payload = {
        "profile": {
            "full_name": "Nombre aportado",
            "email": "given@example.test",
            "skills": ["Python"],
            "title": "Backend Developer",
        }
    }
    saved = client.put(PREFIX + "/profile", json=payload)
    assert saved.status_code == 200, saved.text
    assert not saved.json()["reviewed"]
    assert all(fact["source"] == "user" and fact["verified"] for fact in saved.json()["profile"]["facts"])
    assert client.post(PREFIX + "/profile/review").json()["reviewed"]
    workspace = client.get(PREFIX + "/workspace").json()
    assert workspace["full_name"] == "Nombre aportado" and workspace["email"] == "given@example.test"
    assert client.get(PREFIX + "/profile").json()["profile"]["full_name"] == "Nombre aportado"


def test_other_browser_origins_and_untrusted_hosts_cannot_use_personal_api(client):
    assert (
        client.get(PREFIX + "/workspace", headers={"Origin": "https://unrelated.example"}).status_code == 403
    )
    assert (
        client.post(PREFIX + "/automation/stop", headers={"Origin": "https://unrelated.example"}).status_code
        == 403
    )
    assert client.get(PREFIX + "/workspace", headers={"Host": "unrelated.example"}).status_code == 400
    assert client.get(PREFIX + "/workspace", headers={"Origin": "http://localhost:3000"}).status_code == 200


def test_explicit_legacy_selection_is_persisted(client, legacy_owner, monkeypatch):
    with database.SessionLocal() as db:
        older = User(email="older@example.test", full_name="Older", password_hash="disabled")
        db.add(older)
        db.commit()
    monkeypatch.setattr(get_settings(), "local_user_id", legacy_owner)
    assert client.get(PREFIX + "/workspace").json()["id"] == legacy_owner
    monkeypatch.setattr(get_settings(), "local_user_id", "not-the-owner")
    assert client.get(PREFIX + "/workspace").json()["id"] == legacy_owner


def test_reset_creates_empty_workspace_instead_of_adopting_other_legacy_data(client, headers, legacy_owner):
    current_id = client.get(PREFIX + "/workspace").json()["id"]
    assert current_id != legacy_owner
    assert client.delete(PREFIX + "/workspace").status_code == 204
    fresh = client.get(PREFIX + "/workspace").json()
    assert fresh["id"] not in {current_id, legacy_owner}
    assert fresh["full_name"] == fresh["email"] == ""
