"""Preflight and local browser behavior, without bypassing platform protections."""

import os
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest

from app.automation.browser_manager import BrowserManager, validate_test_url
from app.automation.form_detector import NeedsHumanIntervention, inspect_form
from app.automation.form_filler import fill_known_fields
from app.automation.submission_guard import SubmissionBlocked, SubmissionGuard
from app.integrations.demo import DemoAdapter
from app.integrations.remotive import RemotiveAdapter
from app.schemas import ApplicationRules, CandidateProfile, MatchResult


def guard_input() -> dict[str, Any]:
    return {
        "rules": ApplicationRules(minimum_score=70),
        "profile": CandidateProfile(full_name="Ana Ejemplo", email="ana@example.com", reviewed=True),
        "job": DemoAdapter().search()[0],
        "match": MatchResult(score=90, eligible=True, decision="Elegible"),
        "adapter": DemoAdapter(),
        "approved": True,
        "daily_count": 0,
        "weekly_count": 0,
        "stopped": False,
        "packet": {"source": "demo", "pending_questions": []},
    }


def test_guard_permits_reviewed_approved_demo_without_external_consent() -> None:
    assert SubmissionGuard.check(**guard_input()).allowed


@pytest.mark.parametrize(
    "updates",
    [
        {"stopped": True},
        {"approved": False},
        {"daily_count": 10},
        {"weekly_count": 40},
        {"profile": CandidateProfile(full_name="Ana", email="ana@example.com", reviewed=False)},
        {"profile": CandidateProfile(reviewed=True)},
        {
            "match": MatchResult(
                score=99, eligible=False, decision="Pendiente", blockers=["Licencia desconocida"]
            )
        },
        {"match": MatchResult(score=30, eligible=True, decision="Baja compatibilidad")},
        {"packet": {"pending_questions": ["Visa?"]}},
        {"packet": {"questions": [{"answer": "C1", "verified": False}]}},
        {"packet": {"questions": [{"answer": "C1"}]}},
        {"packet": {"answers": {"english": "C1"}}},
        {"rules": ApplicationRules(permitted_sources=["greenhouse"])},
        {"rules": ApplicationRules(mode="manual")},
        {"automatic": True},
    ],
)
def test_guard_blocks_each_exclusion_independently(updates: dict[str, Any]) -> None:
    values = guard_input()
    values.update(updates)
    decision = SubmissionGuard.check(**values)
    assert not decision.allowed
    assert decision.blockers
    with pytest.raises(SubmissionBlocked):
        decision.require_allowed()


def test_automatic_send_requires_explicit_enablement_and_respects_approval_rule() -> None:
    values = guard_input()
    values.update(
        automatic=True,
        approved=False,
        rules=ApplicationRules(mode="automatic", automatic_enabled=True, requires_approval=False),
    )
    assert SubmissionGuard.check(**values).allowed
    values["rules"] = ApplicationRules(mode="automatic", automatic_enabled=True, requires_approval=True)
    assert not SubmissionGuard.check(**values).allowed


def test_real_source_cannot_be_submitted_through_demo_adapter() -> None:
    values = guard_input()
    values["job"] = values["job"].model_copy(update={"source": "remotive"})
    values["adapter"] = RemotiveAdapter()
    decision = SubmissionGuard.check(**values)
    assert not decision.allowed
    assert any("manual" in blocker for blocker in decision.blockers)
    assert any("consentimiento" in blocker for blocker in decision.blockers)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/form",
        "http://127.0.0.1.evil.example/form",
        "file:///tmp/form.html",
        "http://user:pass@localhost/form",
        "http://localhost@evil.example/form",
        "javascript:alert(1)",
    ],
)
def test_browser_rejects_nonlocal_or_credential_urls(url: str) -> None:
    with pytest.raises(NeedsHumanIntervention):
        validate_test_url(url)


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page = page
        self.selector = selector

    def count(self) -> int:
        if "captcha" in self.selector:
            return int(self.page.captcha)
        if "password" in self.selector:
            return int(self.page.password)
        return len(self.page.controls)

    def evaluate_all(self, script: str, argument: Any = None) -> Any:
        if argument is None:
            return self.page.controls
        self.page.filled.append(argument)
        return None


class FakePage:
    def __init__(
        self, controls: list[dict[str, Any]], *, captcha: bool = False, password: bool = False
    ) -> None:
        self.controls = controls
        self.captcha = captcha
        self.password = password
        self.filled: list[dict[str, str]] = []

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)


def test_form_refuses_unknown_mandatory_questions() -> None:
    page = FakePage([{"name": "work_authorization", "required": True, "type": "text"}])
    with pytest.raises(NeedsHumanIntervention):
        fill_known_fields(page, {"email": "ana@example.com"})
    assert page.filled == []


@pytest.mark.parametrize("protection", ["captcha", "password"])
def test_form_stops_on_human_protections(protection: str) -> None:
    page = FakePage([], **{protection: True})
    with pytest.raises(NeedsHumanIntervention):
        inspect_form(page, {})


def test_external_field_names_are_data_never_css_or_code() -> None:
    name = 'email"] + input[name="secret'
    page = FakePage([{"name": name, "required": True, "type": "text"}])
    assert fill_known_fields(page, {name: "ana@example.com"}) == [name]
    assert page.filled == [{"name": name, "value": "ana@example.com"}]


@pytest.fixture
def form_server() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = b'<form><input name="name" required><input name="email" type="email" required></form>'
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/form"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.browser
@pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1", reason="Set RUN_BROWSER_TESTS=1 with Chromium installed"
)
def test_playwright_fills_controlled_local_form_and_waits_for_approval(form_server: str) -> None:
    manager = BrowserManager()
    answers = {"name": "Ana Ejemplo", "email": "ana@example.com"}
    with manager.session() as page:
        page.goto(form_server, wait_until="domcontentloaded")
        assert set(fill_known_fields(page, answers)) == {"name", "email"}
        assert page.locator('[name="name"]').input_value() == "Ana Ejemplo"
        assert page.locator('[name="email"]').input_value() == "ana@example.com"
        page.set_content('<form><input name="visa" required></form>')
        with pytest.raises(NeedsHumanIntervention):
            fill_known_fields(page, answers)
        page.set_content('<form><input name="email"><div data-captcha></div></form>')
        with pytest.raises(NeedsHumanIntervention):
            fill_known_fields(page, answers)
    result = manager.prepare(form_server, answers)
    assert set(result["filled_fields"]) == {"name", "email"}
    assert result["submitted"] is False
    assert result["requires_approval"] is True
