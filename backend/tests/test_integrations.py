"""Provider fixtures never consume real AI credits or send a real application."""

import httpx
import pytest

from app.integrations import SourceCapabilityError, SourceError, get_source, list_sources
from app.integrations.demo import DemoAdapter
from app.integrations.greenhouse import GreenhouseAdapter
from app.integrations.remotive import RemotiveAdapter


def test_remotive_reads_official_feed_and_preserves_source_link() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 123,
                        "title": "Python Engineer",
                        "company_name": "Example Corp",
                        "url": "https://remotive.com/remote-jobs/software-dev/123",
                        "description": "<p>Build APIs.</p><script>steal()</script>",
                        "candidate_required_location": "Colombia",
                        "publication_date": "2026-10-01T13:00:00",
                        "salary": "$40,000 - $60,000",
                        "tags": ["Python"],
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        jobs = RemotiveAdapter(client).search("python")
    assert len(calls) == 1
    assert str(calls[0].url) == "https://remotive.com/api/remote-jobs"
    assert len(jobs) == 1
    assert jobs[0].source == "remotive"
    assert jobs[0].url.startswith("https://remotive.com/")
    assert jobs[0].work_mode == "remote"
    assert "steal()" not in jobs[0].description
    assert "$40,000" in jobs[0].description
    assert jobs[0].salary_min is None  # Do not guess currency or salary period.


@pytest.mark.parametrize("status", [401, 403])
def test_auth_errors_require_human_without_retry(status: int) -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status))) as client:
        with pytest.raises(SourceError) as caught:
            RemotiveAdapter(client).search()
    assert caught.value.requires_human
    assert not caught.value.transient


def test_rate_limit_exposes_retry_after_without_looping() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(429, headers={"Retry-After": "300"}))
    ) as client:
        with pytest.raises(SourceError) as caught:
            RemotiveAdapter(client).search()
    assert caught.value.transient
    assert caught.value.retry_after == 300


@pytest.mark.parametrize("status", [302, 404, 500])
def test_provider_failure_never_becomes_an_empty_success(status: int) -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status))) as client:
        with pytest.raises(SourceError) as caught:
            RemotiveAdapter(client).search()
    assert caught.value.transient is (status == 500)


def test_greenhouse_keeps_board_in_external_id_and_decodes_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "boards-api.greenhouse.io"
        assert request.url.path == "/v1/boards/exampleco/jobs"
        assert request.url.params["content"] == "true"
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 77,
                        "title": "Backend Engineer",
                        "absolute_url": "https://boards.greenhouse.io/exampleco/jobs/77",
                        "location": {"name": "Remote - Colombia"},
                        "content": "&lt;p&gt;Python &amp;amp; SQL&lt;/p&gt;",
                        "updated_at": "2026-10-01T00:00:00Z",
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        job = GreenhouseAdapter(client).search(board="exampleco")[0]
    assert job.external_id == "exampleco:77"
    assert job.work_mode == "remote"
    assert job.description == "Python & SQL"
    assert job.published_at is None  # Update timestamps must not become publication dates.


@pytest.mark.parametrize("board", [None, "../../secret", "https://evil.example", "x?token=y", "a/b", "a\\b"])
def test_greenhouse_rejects_unsafe_board_before_network(board: str | None) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("No network request may be made for an invalid token.")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError):
            GreenhouseAdapter(client).search(board=board)


def test_greenhouse_detail_can_use_stored_external_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/boards/exampleco/jobs/77"
        return httpx.Response(
            200,
            json={
                "id": 77,
                "title": "Engineer",
                "company_name": "Example Corp",
                "content": "Actual description",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        job = GreenhouseAdapter(client).details("exampleco:77")
    assert job.company == "Example Corp"


def test_only_explicit_demo_provider_supports_sending() -> None:
    sources = {source["name"]: source for source in list_sources()}
    assert sources["demo"]["capabilities"]["submit"]
    assert all(not source["capabilities"]["submit"] for name, source in sources.items() if name != "demo")
    with pytest.raises(SourceCapabilityError):
        get_source("not-supported")
    with pytest.raises(SourceCapabilityError):
        get_source("linkedin").submit("id", {})
    with pytest.raises(SourceCapabilityError):
        get_source("remotive").submit("id", {})


def test_demo_submission_is_offline_identified_and_idempotent() -> None:
    adapter = DemoAdapter()
    first = adapter.submit("application-123", {"source": "demo", "cover_letter": "Verified text"})
    replay = DemoAdapter().submit("application-123", {"source": "demo"})
    assert first == replay
    assert first.submitted and first.confirmed
    assert first.reference.startswith("DEMO-")
    assert first.evidence["simulation"] is True
    assert first.evidence["transport"] == "in_process"
    assert all(job.title.startswith("[PRUEBA]") for job in adapter.search())


def test_demo_refuses_non_demo_source_and_unanswered_questions() -> None:
    with pytest.raises(SourceError):
        DemoAdapter().submit("id", {"source": "greenhouse"})
    with pytest.raises(SourceError) as caught:
        DemoAdapter().submit("id", {"pending_questions": ["Work authorization?"]})
    assert caught.value.requires_human


def test_malformed_provider_response_is_explicit_failure() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"changed": []}))
    ) as client:
        with pytest.raises(SourceError):
            RemotiveAdapter(client).search()
