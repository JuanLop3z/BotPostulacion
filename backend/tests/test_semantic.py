"""Opt-in semantic matching tests through native Ollama HTTP with a controlled transport."""

import json
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.database import session as database
from app.integrations.demo import DemoAdapter
from app.models import EmbeddingCache, Evaluation
from app.schemas import CandidateProfile, ContextBundle, JobData
from app.services import semantic_matching
from app.services.ai_provider import OllamaProvider
from app.services.job_matcher import match_job

PREFIX = "/api/v1"


@pytest.fixture
def ollama_requests(monkeypatch) -> list[dict[str, Any]]:
    """Use actual Ollama serialization/validation while preventing any real HTTP request."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_embeddings", True)
    monkeypatch.setattr(settings, "llm_endpoint", "http://localhost:11434")
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "embedding_model", "controlled-embedding")
    captured: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        body = json.loads(request.content)
        assert body["truncate"] is True
        captured.append(body)
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0, 0.0]], "prompt_eval_count": 3})

    def controlled_provider() -> OllamaProvider:
        return OllamaProvider(
            settings.llm_endpoint,
            embedding_model=settings.embedding_model,
            transport=httpx.MockTransport(handle),
        )

    monkeypatch.setattr(semantic_matching, "provider", controlled_provider)
    return captured


def enable_consent(client, headers) -> None:
    context = client.get(PREFIX + "/context", headers=headers).json()
    context.pop("version")
    context["rules"]["llm_consent"] = True
    response = client.put(PREFIX + "/context", headers=headers, json=context)
    assert response.status_code == 200, response.text


def search_demo(client, headers) -> list[dict[str, Any]]:
    response = client.post(PREFIX + "/jobs/search", headers=headers, json={"source": "demo"})
    assert response.status_code == 202, response.text
    task = client.get(PREFIX + "/tasks/" + response.json()["task_id"], headers=headers)
    assert task.json()["status"] == "SUCCESS", task.text
    result = client.get(PREFIX + "/jobs", headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


def test_no_embedding_call_or_cache_without_consent(client, headers, ready_profile, ollama_requests) -> None:
    rows = search_demo(client, headers)
    assert rows
    assert ollama_requests == []
    assert all(row["match"]["method"] == "rules_keywords" for row in rows)
    with database.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(EmbeddingCache)) == 0


def test_opt_in_persists_real_vectors_and_reuses_evaluations(
    client,
    headers,
    ready_profile,
    ollama_requests,
) -> None:
    enable_consent(client, headers)
    rows = search_demo(client, headers)
    assert len(ollama_requests) == len(rows) + 1  # One candidate vector shared across its job evaluations.
    assert all(row["match"]["method"] == "rules_keywords_embeddings" for row in rows)
    assert sum(item["input"].startswith("Competencias verificadas:") for item in ollama_requests) == 1
    serialized_inputs = " ".join(item["input"] for item in ollama_requests)
    assert "candidate@example.test" not in serialized_inputs
    assert "Ana Prueba" not in serialized_inputs
    with database.SessionLocal() as db:
        vectors = list(db.scalars(select(EmbeddingCache)))
        assert len(vectors) == len(rows) + 1
        assert all(list(vector.vector) == [1.0, 0.0, 0.0] for vector in vectors)
        assert all(vector.model == "controlled-embedding" for vector in vectors)
        assert db.scalar(select(func.count()).select_from(Evaluation)) == len(rows)
    before = len(ollama_requests)
    assert client.get(PREFIX + "/jobs", headers=headers).status_code == 200
    assert client.post(PREFIX + "/jobs/rematch", headers=headers).json() == {"evaluated": len(rows)}
    assert len(ollama_requests) == before


def test_model_change_invalidates_embeddings_and_evaluation_cache(
    client,
    headers,
    ready_profile,
    ollama_requests,
    monkeypatch,
) -> None:
    enable_consent(client, headers)
    rows = search_demo(client, headers)
    first_count = len(ollama_requests)
    monkeypatch.setattr(get_settings(), "embedding_model", "different-controlled-model")
    response = client.post(PREFIX + "/jobs/rematch", headers=headers)
    assert response.status_code == 200, response.text
    assert len(ollama_requests) == first_count * 2
    assert all(request["model"] == "different-controlled-model" for request in ollama_requests[first_count:])
    with database.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(EmbeddingCache)) == first_count * 2
        assert db.scalar(select(func.count()).select_from(Evaluation)) == len(rows) * 2


def test_embedding_cache_preserves_legacy_owner_scoping(
    client,
    headers,
    ready_profile,
    ollama_requests,
    legacy_owner,
) -> None:
    first_user = client.get(PREFIX + "/workspace", headers=headers).json()["id"]
    second_user = legacy_owner
    profile = CandidateProfile.model_validate(ready_profile["profile"])
    job = DemoAdapter().search()[0]
    with database.SessionLocal() as db:
        assert semantic_matching.similarity(db, first_user, profile, job, consent=True) == 1
        db.commit()
        assert len(ollama_requests) == 2
        assert semantic_matching.similarity(db, second_user, profile, job, consent=True) == 1
        db.commit()
        assert len(ollama_requests) == 4
        first = list(db.scalars(select(EmbeddingCache).where(EmbeddingCache.user_id == first_user)))
        second = list(db.scalars(select(EmbeddingCache).where(EmbeddingCache.user_id == second_user)))
        assert len(first) == len(second) == 2
        assert {row.cache_key for row in first} == {row.cache_key for row in second}
        assert {row.id for row in first}.isdisjoint({row.id for row in second})
    with database.SessionLocal() as db:
        from app.models import User

        db.delete(db.get(User, second_user))
        db.commit()
        assert db.scalar(select(func.count()).select_from(EmbeddingCache)) == 2
        assert all(row.user_id == first_user for row in db.scalars(select(EmbeddingCache)))


def test_perfect_semantic_similarity_does_not_override_missing_mandatory_requirement(
    client,
    headers,
    ready_profile,
    ollama_requests,
) -> None:
    enable_consent(client, headers)
    rows = search_demo(client, headers)
    blocked = next(row for row in rows if row["external_id"] == "demo-ml-license")
    assert blocked["match"]["method"] == "rules_keywords_embeddings"
    assert not blocked["match"]["eligible"]
    assert any("Licencia profesional" in blocker for blocker in blocked["match"]["blockers"])
    context_data = client.get(PREFIX + "/context", headers=headers).json()
    context_data.pop("version")
    profile = CandidateProfile.model_validate(ready_profile["profile"])
    job = JobData.model_validate(
        {key: value for key, value in blocked.items() if key not in {"id", "match", "application_state"}}
    )
    baseline = match_job(profile, job, ContextBundle.model_validate(context_data))
    assert not baseline.eligible
    assert blocked["match"]["score"] >= baseline.score
    prepared = client.post(PREFIX + "/applications", headers=headers, json={"job_id": blocked["id"]})
    assert prepared.status_code == 201, prepared.text
    assert prepared.json()["state"] == "REJECTED_BY_RULES"


def test_unreviewed_profile_or_disabled_feature_never_requests_embeddings(
    client,
    headers,
    ready_profile,
    ollama_requests,
    monkeypatch,
) -> None:
    user = client.get(PREFIX + "/workspace", headers=headers).json()["id"]
    profile = CandidateProfile.model_validate(ready_profile["profile"])
    job = DemoAdapter().search()[0]
    with database.SessionLocal() as db:
        profile.reviewed = False
        assert semantic_matching.similarity(db, user, profile, job, consent=True) is None
        profile.reviewed = True
        monkeypatch.setattr(get_settings(), "enable_embeddings", False)
        assert semantic_matching.similarity(db, user, profile, job, consent=True) is None
    assert ollama_requests == []


def test_revoking_consent_stops_external_calls_and_uses_local_evaluation(
    client,
    headers,
    ready_profile,
    ollama_requests,
) -> None:
    enable_consent(client, headers)
    rows = search_demo(client, headers)
    assert len(ollama_requests) == len(rows) + 1
    context = client.get(PREFIX + "/context", headers=headers).json()
    context.pop("version")
    context["rules"]["llm_consent"] = False
    assert client.put(PREFIX + "/context", headers=headers, json=context).status_code == 200
    before = len(ollama_requests)
    local_rows = client.get(PREFIX + "/jobs", headers=headers).json()
    assert len(local_rows) == len(rows)
    assert all(row["match"]["method"] == "rules_keywords" for row in local_rows)
    assert len(ollama_requests) == before
