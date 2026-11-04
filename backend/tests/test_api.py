from app.core.security import decrypt_document
from app.database import session as database
from app.models import Application, AuditEvent, Job, SearchRun
from app.services.application_manager import TRANSITIONS

PREFIX = "/api/v1"


def eligible_job(demo_jobs):
    return next(row for row in demo_jobs if row["match"]["eligible"])


def prepare(client, headers, demo_jobs):
    job = eligible_job(demo_jobs)
    response = client.post(PREFIX + "/applications", headers=headers, json={"job_id": job["id"]})
    assert response.status_code == 201, response.text
    assert response.json()["state"] == "PENDING_APPROVAL", response.text
    return response.json()


def test_personal_workspace_needs_no_login_or_token(client):
    assert client.get("/health").status_code == 200
    assert client.get(PREFIX + "/dashboard").status_code == 200
    assert client.get(PREFIX + "/jobs").status_code == 200
    workspace = client.get(PREFIX + "/workspace").json()
    assert workspace["mode"] == "personal" and workspace["email"] == ""
    assert client.get(PREFIX + "/workspace").json()["id"] == workspace["id"]


def test_login_and_registration_routes_removed(client):
    payload = {"email": "candidate@example.test", "password": "strong-password-for-tests"}
    assert client.post(PREFIX + "/auth/register", json=payload).status_code == 404
    assert client.post(PREFIX + "/auth/login", json=payload).status_code == 404
    assert "securitySchemes" not in client.get("/openapi.json").json().get("components", {})


def test_document_encryption_and_profile_versions(client, headers, ready_profile):
    from app.core.config import get_settings

    original = list((get_settings().storage_dir / "cv").glob("*.enc"))[0].read_bytes()
    assert b"candidate@example.test" not in original
    assert b"candidate@example.test" in decrypt_document(original)
    response = client.get(PREFIX + "/profile", headers=headers).json()
    assert response["version"] == 2 and response["reviewed"]
    assert any(f["source"] == "cv" for f in response["profile"]["facts"])


def test_context_yaml_defaults_and_versioned_edit(client, headers):
    context = client.get(PREFIX + "/context", headers=headers).json()
    assert context["version"] == 1
    context.pop("version")
    context["custom_instructions"] = "Priorizar backend"
    saved = client.put(PREFIX + "/context", headers=headers, json=context)
    assert saved.json()["version"] == 2
    context["rules"]["max_daily"] = -1
    assert client.put(PREFIX + "/context", headers=headers, json=context).status_code == 422


def test_search_deduplication_and_cache(client, headers, demo_jobs, monkeypatch):
    from app.integrations.demo import DemoAdapter

    def forbidden(*args, **kwargs):
        raise AssertionError("Cached source must not be fetched twice")

    monkeypatch.setattr(DemoAdapter, "search", forbidden)
    response = client.post(PREFIX + "/jobs/search", headers=headers, json={"source": "demo"})
    task = client.get(PREFIX + "/tasks/" + response.json()["task_id"], headers=headers).json()
    assert task["status"] == "SUCCESS", task
    assert task["result"]["inserted"] == 0
    assert task["result"]["duplicates"] == len(demo_jobs)
    assert len(client.get(PREFIX + "/jobs", headers=headers).json()) == len(demo_jobs)


def test_provider_identity_survives_title_changes(client, headers, demo_jobs):
    from sqlalchemy import select

    from app.models import SourceCache

    with database.SessionLocal() as db:
        cache = db.execute(select(SourceCache).where(SourceCache.key == "demo:")).scalar_one()
        changed = [dict(item) for item in cache.data]
        changed[0]["title"] = "A new title for the very same provider vacancy"
        changed[0]["location"] = "Different office"
        cache.data = changed
        db.commit()
    response = client.post(PREFIX + "/jobs/search", headers=headers, json={"source": "demo"})
    task = client.get(PREFIX + "/tasks/" + response.json()["task_id"], headers=headers).json()
    assert task["status"] == "SUCCESS", task
    assert task["result"]["inserted"] == 0
    assert len(client.get(PREFIX + "/jobs", headers=headers).json()) == len(demo_jobs)


def test_prepare_approve_demo_submit_idempotency(client, headers, demo_jobs):
    application = prepare(client, headers, demo_jobs)
    app_id = application["id"]
    assert (
        client.post(PREFIX + "/applications", headers=headers, json={"job_id": application["job_id"]}).json()[
            "id"
        ]
        == app_id
    )
    assert client.post(f"{PREFIX}/applications/{app_id}/submit", headers=headers).status_code == 409
    assert client.post(f"{PREFIX}/applications/{app_id}/approve", headers=headers).json()["approved"]
    assert client.post(PREFIX + "/automation/start", headers=headers).status_code == 200
    submitted = client.post(f"{PREFIX}/applications/{app_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["state"] == "CONFIRMED"
    assert submitted.json()["evidence"]["simulation"] is True
    again = client.post(f"{PREFIX}/applications/{app_id}/submit", headers=headers).json()
    assert again["result_reference"] == submitted.json()["result_reference"]
    assert again["attempts"] == 1


def test_emergency_stop_prevents_new_submissions(client, headers, demo_jobs):
    application = prepare(client, headers, demo_jobs)
    client.post(f"{PREFIX}/applications/{application['id']}/approve", headers=headers)
    client.post(PREFIX + "/automation/start", headers=headers)
    client.post(PREFIX + "/automation/stop", headers=headers)
    response = client.post(f"{PREFIX}/applications/{application['id']}/submit", headers=headers)
    assert response.status_code == 409
    assert "parada" in response.json()["detail"].lower()


def test_context_edit_invalidates_approval_and_can_regenerate(client, headers, demo_jobs):
    application = prepare(client, headers, demo_jobs)
    context = client.get(PREFIX + "/context", headers=headers).json()
    context.pop("version")
    context["custom_instructions"] = "Priorizar backend Python"
    client.put(PREFIX + "/context", headers=headers, json=context)
    assert (
        client.post(f"{PREFIX}/applications/{application['id']}/approve", headers=headers).status_code == 409
    )
    rebuilt = client.post(f"{PREFIX}/applications/{application['id']}/regenerate", headers=headers)
    assert rebuilt.status_code == 200, rebuilt.text
    assert rebuilt.json()["state"] == "PENDING_APPROVAL"
    assert (
        client.post(f"{PREFIX}/applications/{application['id']}/approve", headers=headers).status_code == 200
    )


def test_legacy_storage_is_not_exposed_in_personal_workspace(client, headers, demo_jobs, legacy_owner):
    own = prepare(client, headers, demo_jobs)
    with database.SessionLocal() as db:
        reference = db.get(Job, own["job_id"])
        hidden = Job(
            user_id=legacy_owner,
            fingerprint="legacy-fingerprint",
            source="demo",
            external_id="legacy-job",
            data=reference.data,
        )
        db.add(hidden)
        db.commit()
        hidden_id = hidden.id
    assert hidden_id not in {row["id"] for row in client.get(PREFIX + "/jobs").json()}
    assert client.post(PREFIX + "/applications", json={"job_id": hidden_id}).status_code == 404
    assert (
        client.get(PREFIX + "/workspace", headers={"Authorization": "Bearer old-token"}).json()["id"]
        != legacy_owner
    )


def test_daily_limit_and_manual_confirmation_states(client, headers, demo_jobs):
    context = client.get(PREFIX + "/context", headers=headers).json()
    context.pop("version")
    context["rules"]["max_daily"] = 0
    client.put(PREFIX + "/context", headers=headers, json=context)
    application = prepare(client, headers, demo_jobs)
    path = f"{PREFIX}/applications/{application['id']}"
    client.post(path + "/approve", headers=headers)
    client.post(PREFIX + "/automation/start", headers=headers)
    response = client.post(path + "/submit", headers=headers)
    assert response.status_code == 409 and "diario" in response.json()["detail"]
    manual = client.post(path + "/manual-confirm", headers=headers, json={"confirmed": False})
    assert manual.json()["state"] == "SUBMITTED"
    client.post(PREFIX + "/profile/review", headers=headers)  # Historical receipt still can be recorded.
    confirmation = client.post(path + "/manual-confirm", headers=headers, json={"confirmed": True})
    assert confirmation.json()["state"] == "CONFIRMED"
    assert confirmation.json()["evidence"]["platform_verified"] is False


def test_profile_fact_provenance_cannot_be_rewritten(client, headers, ready_profile):
    before = client.get(PREFIX + "/profile", headers=headers).json()["profile"]
    before["facts"].append({"field": "skills", "value": "ImaginaryCert", "source": "cv", "verified": True})
    response = client.put(PREFIX + "/profile", headers=headers, json={"profile": before})
    assert not any(fact["value"] == "ImaginaryCert" for fact in response.json()["profile"]["facts"])
    assert response.json()["reviewed"] is False


def test_context_proposals_require_specific_verification(client, headers, ready_profile):
    context = client.get(PREFIX + "/context", headers=headers).json()
    context.pop("version")
    context["candidate_context"] = "Habilidades confirmadas: Rust"
    client.put(PREFIX + "/context", headers=headers, json=context)
    enriched = client.post(PREFIX + "/profile/enrich", headers=headers)
    assert enriched.status_code == 200, enriched.text
    fact = next(f for f in enriched.json()["profile"]["facts"] if f["value"] == "Rust")
    assert fact["source"] == "context" and not fact["verified"]
    verified = client.post(
        PREFIX + "/profile/verify-fact", headers=headers, json={"field": "skills", "value": "Rust"}
    )
    fact = next(f for f in verified.json()["profile"]["facts"] if f["value"] == "Rust")
    assert fact["verified"] and fact["source"] == "user"


def test_dashboard_csv_and_workspace_reset(client, headers, demo_jobs):
    prepare(client, headers, demo_jobs)
    dashboard = client.get(PREFIX + "/dashboard", headers=headers).json()
    assert dashboard["jobs"] == len(demo_jobs)
    assert dashboard["applications"] == 1
    assert dashboard["ai_cost_usd"] is None
    csv = client.get(PREFIX + "/reports/applications.csv", headers=headers)
    assert csv.status_code == 200 and "cargo" in csv.text
    assert client.delete(PREFIX + "/workspace").status_code == 204
    assert client.get(PREFIX + "/profile").json() is None
    with database.SessionLocal() as db:
        from sqlalchemy import func, select

        for model in (Job, Application, AuditEvent, SearchRun):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_invalid_documents_and_search_input(client, headers):
    assert (
        client.post(
            PREFIX + "/cv", headers=headers, files={"file": ("bad.pdf", b"fake pdf", "application/pdf")}
        ).status_code
        == 422
    )
    assert (
        client.post(PREFIX + "/jobs/search", headers=headers, json={"source": "greenhouse"}).status_code
        == 422
    )
    assert (
        client.post(
            PREFIX + "/jobs/search", headers=headers, json={"source": "greenhouse", "board": "../private"}
        ).status_code
        == 422
    )


def test_state_machine_terminal_states_and_transitions():
    assert TRANSITIONS["CONFIRMED"] == {"WITHDRAWN"}
    assert TRANSITIONS["WITHDRAWN"] == set()
    assert "CONFIRMED" not in TRANSITIONS["PREPARED"]
