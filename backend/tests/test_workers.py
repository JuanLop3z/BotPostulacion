"""Queue behavior is exercised directly, without a broker, provider or real submission."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select

from app.database import session as database
from app.integrations import SourceError
from app.integrations.demo import DemoAdapter
from app.integrations.remotive import RemotiveAdapter
from app.models import Application, Job, SearchRun, SourceCache, User
from app.services.search_pipeline import process_search

PREFIX = "/api/v1"


class RequestedRetry(Exception):
    pass


@pytest.fixture
def worker_modules(client, monkeypatch):
    from app.workers import scheduler, tasks

    # The API fixture replaces the DB factory. These imported-by-value aliases
    # must use that same isolated database instead of the developer's local DB.
    for module in (scheduler, tasks):
        monkeypatch.setattr(module, "SessionLocal", database.SessionLocal)
    return tasks, scheduler


def configure_retries(client, headers: dict[str, str], maximum: int) -> str:
    context = client.get(PREFIX + "/context", headers=headers).json()
    context.pop("version", None)
    context["rules"]["max_retries"] = maximum
    assert client.put(PREFIX + "/context", headers=headers, json=context).status_code == 200
    return client.get(PREFIX + "/workspace", headers=headers).json()["id"]


def create_run(
    user_id: str,
    *,
    scheduled: bool = False,
    status: str = "PENDING",
    started_at: datetime | None = None,
    source: str = "demo",
) -> str:
    with database.SessionLocal() as db:
        run = SearchRun(
            user_id=user_id,
            source=source,
            query="",
            scheduled=scheduled,
            status=status,
            started_at=started_at,
        )
        db.add(run)
        db.commit()
        return run.id


@pytest.mark.parametrize(
    ("maximum", "retries", "expect_retry"),
    [
        (0, 0, False),
        (1, 0, True),
        (1, 1, False),
        (3, 2, True),
        (5, 5, False),
    ],
)
def test_worker_retry_respects_per_user_limit(
    client, headers, worker_modules, monkeypatch, maximum: int, retries: int, expect_retry: bool
) -> None:
    tasks, _ = worker_modules
    user_id = configure_retries(client, headers, maximum)
    run_id = create_run(user_id)
    retry_calls: list[dict[str, Any]] = []

    def unavailable(*args: Any, **kwargs: Any) -> list[Any]:
        raise SourceError("Fallo transitorio controlado", transient=True, retry_after=300)

    def request_retry(**kwargs: Any) -> None:
        retry_calls.append(kwargs)
        raise RequestedRetry

    monkeypatch.setattr(DemoAdapter, "search", unavailable)
    monkeypatch.setattr(tasks.search_task, "retry", request_retry)
    tasks.search_task.push_request(retries=retries)
    try:
        with pytest.raises(RequestedRetry if expect_retry else SourceError):
            tasks.search_task.run(run_id)
    finally:
        tasks.search_task.pop_request()
    assert bool(retry_calls) is expect_retry
    if retry_calls:
        assert retry_calls[0]["countdown"] >= 300  # Honor provider Retry-After.
    with database.SessionLocal() as db:
        run = db.get(SearchRun, run_id)
        assert run is not None
        assert run.status == ("RETRY_PENDING" if expect_retry else "FAILED")
        if expect_retry:
            assert run.next_attempt_at is not None
            due = run.next_attempt_at
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            assert (due - datetime.now(UTC)).total_seconds() >= 295


@pytest.mark.parametrize(("transient", "human"), [(False, True), (True, True), (False, False)])
def test_worker_never_retries_human_or_permanent_errors(
    client, headers, worker_modules, monkeypatch, transient: bool, human: bool
) -> None:
    tasks, _ = worker_modules
    user_id = configure_retries(client, headers, 5)
    run_id = create_run(user_id)

    def requires_intervention(*args: Any, **kwargs: Any) -> list[Any]:
        raise SourceError("Protección o error permanente", transient=transient, requires_human=human)

    def forbidden_retry(**kwargs: Any) -> None:
        pytest.fail("Un error de autenticación/CAPTCHA/permanente nunca debe reintentarse.")

    monkeypatch.setattr(DemoAdapter, "search", requires_intervention)
    monkeypatch.setattr(tasks.search_task, "retry", forbidden_retry)
    tasks.search_task.push_request(retries=0)
    try:
        with pytest.raises(SourceError):
            tasks.search_task.run(run_id)
    finally:
        tasks.search_task.pop_request()


def test_scheduled_job_stopped_before_execution_never_queries_provider(
    client, headers, worker_modules, monkeypatch
) -> None:
    user_id = configure_retries(client, headers, 0)
    run_id = create_run(user_id, scheduled=True)

    def forbidden(*args: Any, **kwargs: Any) -> list[Any]:
        pytest.fail("Una búsqueda programada detenida no debe consultar al proveedor.")

    monkeypatch.setattr(DemoAdapter, "search", forbidden)
    result = process_search(run_id)
    assert result["status"] == "SKIPPED"
    with database.SessionLocal() as db:
        run = db.get(SearchRun, run_id)
        assert run is not None and run.status == "SKIPPED"
        assert db.scalar(select(func.count()).select_from(Job)) == 0


def test_stop_after_provider_read_prevents_scheduled_persistence(
    client, headers, worker_modules, monkeypatch
) -> None:
    user_id = configure_retries(client, headers, 0)
    with database.SessionLocal() as db:
        user = db.get(User, user_id)
        assert user is not None
        user.automation_enabled = True
        # Existing cache row avoids SQLite's database-wide write lock during
        # initialization; PostgreSQL uses row locks for this race in production.
        db.add(SourceCache(key="demo:", data=[]))
        db.commit()
    run_id = create_run(user_id, scheduled=True)
    jobs = DemoAdapter().search()

    def stop_during_read(*args: Any, **kwargs: Any):
        # This happens between the queue's initial stop check and ingestion's
        # locked check, reproducing an emergency stop while a GET is in flight.
        with database.SessionLocal() as db:
            user = db.get(User, user_id)
            assert user is not None
            user.automation_enabled = False
            db.commit()
        return jobs

    monkeypatch.setattr(DemoAdapter, "search", stop_during_read)
    result = process_search(run_id)
    assert result["status"] == "SKIPPED"
    with database.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Job)) == 0


def test_orphan_started_search_recovers_after_lease(client, headers, worker_modules) -> None:
    user_id = configure_retries(client, headers, 0)
    run_id = create_run(user_id, status="STARTED", started_at=datetime.now(UTC) - timedelta(minutes=8))
    result = process_search(run_id)
    assert result["inserted"] > 0
    with database.SessionLocal() as db:
        run = db.get(SearchRun, run_id)
        assert run is not None and run.status == "SUCCESS"


def test_live_started_lease_prevents_duplicate_provider_read(
    client, headers, worker_modules, monkeypatch
) -> None:
    user_id = configure_retries(client, headers, 0)
    run_id = create_run(user_id, status="STARTED", started_at=datetime.now(UTC))

    def forbidden(*args: Any, **kwargs: Any):
        pytest.fail("Una entrega duplicada no debe consultar al proveedor mientras la lease siga vigente.")

    monkeypatch.setattr(DemoAdapter, "search", forbidden)
    assert process_search(run_id)["status"] == "STARTED"


def test_scheduler_does_not_enqueue_for_stopped_user(client, headers, worker_modules, monkeypatch) -> None:
    _, scheduler = worker_modules
    configure_retries(client, headers, 0)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("El scheduler no debe encolar búsquedas cuando el usuario ha detenido la automatización.")

    monkeypatch.setattr(scheduler.search_task, "delay", forbidden)
    scheduler.schedule_searches()
    with database.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SearchRun)) == 0


def test_scheduler_recovers_stale_queue_deliveries_with_bounded_attempts(
    client, headers, worker_modules, monkeypatch
) -> None:
    _, scheduler = worker_modules
    user_id = configure_retries(client, headers, 1)
    old = datetime.now(UTC) - timedelta(minutes=15)
    recoverable = create_run(user_id, status="STARTED", started_at=old)
    exhausted = create_run(user_id, status="STARTED", started_at=old)
    stopped = create_run(user_id, scheduled=True, status="STARTED", started_at=old)
    current = create_run(user_id, status="STARTED", started_at=datetime.now(UTC))
    with database.SessionLocal() as db:
        row = db.get(SearchRun, exhausted)
        assert row is not None
        row.attempts = 2  # Initial attempt + one permitted retry have both been used.
        db.commit()
    queued: list[str] = []
    monkeypatch.setattr(scheduler, "enqueue", queued.append)
    assert scheduler.recover_stalled_runs() == 1
    assert queued == [recoverable]
    with database.SessionLocal() as db:
        assert db.get(SearchRun, recoverable).status == "RETRY_PENDING"
        assert db.get(SearchRun, exhausted).status == "FAILED"
        assert db.get(SearchRun, stopped).status == "SKIPPED"
        assert db.get(SearchRun, current).status == "STARTED"


def test_scheduler_enqueues_one_scheduled_search_per_source_interval(
    client, headers, worker_modules, monkeypatch
) -> None:
    _, scheduler = worker_modules
    user_id = configure_retries(client, headers, 0)
    context = client.get(PREFIX + "/context", headers=headers).json()
    context.pop("version")
    context["rules"]["permitted_sources"] = ["demo"]
    assert client.put(PREFIX + "/context", headers=headers, json=context).status_code == 200
    with database.SessionLocal() as db:
        user = db.get(User, user_id)
        assert user is not None
        user.automation_enabled = True
        db.commit()
    queued: list[str] = []
    monkeypatch.setattr(scheduler, "enqueue", queued.append)
    scheduler.schedule_searches()
    scheduler.schedule_searches()
    assert len(queued) == 1
    with database.SessionLocal() as db:
        row = db.get(SearchRun, queued[0])
        assert row is not None and row.scheduled and row.source == "demo"


def test_broker_failure_is_recorded_without_leaking_exception(
    client, headers, worker_modules, monkeypatch
) -> None:
    _, scheduler = worker_modules
    user_id = configure_retries(client, headers, 0)
    run_id = create_run(user_id)

    def broker_down(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("redis://private:secret@internal-host:6379")

    monkeypatch.setattr(scheduler.search_task, "delay", broker_down)
    scheduler.enqueue(run_id)
    with database.SessionLocal() as db:
        run = db.get(SearchRun, run_id)
        assert run is not None and run.status == "FAILED"
        assert "secret" not in (run.error or "")


def test_worker_runs_authorized_demo_batch_with_quota_and_idempotency(
    client, headers, ready_profile, worker_modules
) -> None:
    tasks, _ = worker_modules
    user_id = client.get(PREFIX + "/workspace", headers=headers).json()["id"]
    context = client.get(PREFIX + "/context", headers=headers).json()
    context.pop("version")
    context["rules"].update(
        mode="automatic",
        automatic_enabled=True,
        requires_approval=False,
        max_daily=1,
        permitted_sources=["demo"],
    )
    assert client.put(PREFIX + "/context", headers=headers, json=context).status_code == 200
    assert client.post(PREFIX + "/automation/start", headers=headers).status_code == 200
    run_id = create_run(user_id, scheduled=True)
    result = tasks.search_task.run(run_id)
    assert result["submitted"] == 1
    with database.SessionLocal() as db:
        applications = list(db.scalars(select(Application).where(Application.user_id == user_id)))
        submitted = [application for application in applications if application.submitted_at]
        assert len(submitted) == 1
        assert submitted[0].state == "CONFIRMED"
        assert submitted[0].evidence["simulation"] is True
        assert submitted[0].attempts == 1
        assert any(application.state == "REJECTED_BY_RULES" for application in applications)
    # A redelivery after successful processing reuses existing applications.
    repeated = tasks.search_task.run(run_id)
    assert repeated["submitted"] == 0
    with database.SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Application).where(Application.submitted_at.is_not(None))
            )
            == 1
        )


def test_retry_deadline_prevents_early_delivery_and_scheduler_recovery(
    client, headers, worker_modules, monkeypatch
) -> None:
    _, scheduler = worker_modules
    user_id = configure_retries(client, headers, 2)
    run_id = create_run(user_id, status="RETRY_PENDING", started_at=datetime.now(UTC) - timedelta(minutes=30))
    with database.SessionLocal() as db:
        run = db.get(SearchRun, run_id)
        assert run is not None
        run.next_attempt_at = datetime.now(UTC) + timedelta(hours=6)
        run.attempts = 1
        db.commit()

    def forbidden(*args: Any, **kwargs: Any):
        pytest.fail("Una entrega anticipada no debe ignorar Retry-After.")

    queued: list[str] = []
    monkeypatch.setattr(DemoAdapter, "search", forbidden)
    monkeypatch.setattr(scheduler, "enqueue", queued.append)
    assert process_search(run_id)["status"] == "RETRY_PENDING"
    assert scheduler.recover_stalled_runs() == 0
    assert queued == []
    with database.SessionLocal() as db:
        run = db.get(SearchRun, run_id)
        assert run is not None
        run.next_attempt_at = datetime.now(UTC) - timedelta(minutes=8)
        db.commit()
    assert scheduler.recover_stalled_runs() == 1
    assert queued == [run_id]


@pytest.mark.parametrize(("source", "delay", "minimum"), [("demo", 3600, 3500), ("remotive", 60, 21500)])
def test_provider_failure_cooldown_is_shared_across_users_and_queries(
    client, headers, worker_modules, monkeypatch, legacy_owner, source: str, delay: int, minimum: int
) -> None:
    user_id = configure_retries(client, headers, 2)
    first_run = create_run(user_id, source=source)
    calls: list[int] = []

    def rate_limited(*args: Any, **kwargs: Any):
        calls.append(1)
        raise SourceError("Proveedor limitado", transient=True, retry_after=delay)

    monkeypatch.setattr(DemoAdapter if source == "demo" else RemotiveAdapter, "search", rate_limited)
    with pytest.raises(SourceError):
        process_search(first_run)
    with database.SessionLocal() as db:
        cache = db.get(SourceCache, f"{source}:")
        assert cache is not None and cache.next_allowed_at is not None
        due = cache.next_allowed_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        assert (due - datetime.now(UTC)).total_seconds() >= minimum
    second_run = create_run(legacy_owner, source=source)
    with database.SessionLocal() as db:
        run = db.get(SearchRun, second_run)
        assert run is not None
        run.query = "another query"
        db.commit()
    with pytest.raises(SourceError) as caught:
        process_search(second_run)
    assert calls == [1]
    assert caught.value.transient and caught.value.retry_after is not None
    assert caught.value.retry_after >= minimum - 100
