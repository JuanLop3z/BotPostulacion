"""Optional Playwright harness for local test forms. Not a real-platform connector."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlsplit

from app.automation.form_detector import NeedsHumanIntervention
from app.automation.form_filler import fill_known_fields

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def validate_test_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in LOOPBACK_HOSTS
        or parsed.username
        or parsed.password
    ):
        raise NeedsHumanIntervention("El navegador de pruebas sólo admite formularios del equipo local.")
    return url


class BrowserManager:
    @contextmanager
    def session(self) -> Iterator[Any]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Instale la dependencia opcional playwright y su navegador Chromium.") from exc
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(service_workers="block", accept_downloads=False)

            def local_requests_only(route: Any) -> None:
                try:
                    validate_test_url(route.request.url)
                except NeedsHumanIntervention:
                    route.abort("blockedbyclient")
                else:
                    route.continue_()

            context.route("**/*", local_requests_only)
            context.route_web_socket("**/*", lambda websocket: websocket.close())
            page = context.new_page()
            try:
                yield page
            finally:
                context.close()
                browser.close()

    def prepare(self, url: str, answers: dict[str, str]) -> dict[str, Any]:
        validate_test_url(url)
        with self.session() as page:
            page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            validate_test_url(page.url)
            filled = fill_known_fields(page, answers)
            return {"filled_fields": filled, "submitted": False, "requires_approval": True}
