"""Small parsing helpers; external HTML remains untrusted plain data."""

import html
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.integrations.base import SourceError

MAX_RESPONSE_BYTES = 12 * 1024 * 1024
MAX_DESCRIPTION_CHARS = 60_000


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth += 1
        if tag in {"br", "p", "li", "div", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        if tag in {"p", "li", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def plain_text(value: Any) -> str:
    parser = _TextParser()
    # Greenhouse can double-encode its content. Decode markup before discarding it.
    parser.feed(html.unescape(html.unescape(str(value or "")))[: MAX_DESCRIPTION_CHARS * 2])
    return re.sub(r"\n{3,}", "\n\n", "".join(parser.parts)).strip()[:MAX_DESCRIPTION_CHARS]


def safe_job_url(value: Any, *, fallback: str) -> str:
    url = str(value or "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return fallback
    return url


def publication_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def json_response(client: httpx.Client, url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = client.get(url, params=params, timeout=25, follow_redirects=False)
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise SourceError(
            "El proveedor no respondió; se puede reintentar más tarde.", transient=True
        ) from exc
    if response.status_code in {401, 403}:
        raise SourceError("El proveedor requiere autorización o intervención humana.", requires_human=True)
    if response.status_code == 429:
        header = response.headers.get("Retry-After", "")
        delay = min(int(header), 86_400) if header.isdigit() else 21_600
        raise SourceError("El proveedor alcanzó su límite de consultas.", transient=True, retry_after=delay)
    if response.status_code >= 500:
        raise SourceError("Error temporal en el proveedor.", transient=True)
    if not response.is_success:
        raise SourceError(f"No se pudo consultar el proveedor (HTTP {response.status_code}).")
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise SourceError("La respuesta del proveedor supera el límite permitido.")
    try:
        data = response.json()
    except ValueError as exc:
        raise SourceError("El proveedor no devolvió un documento JSON válido.") from exc
    if not isinstance(data, dict):
        raise SourceError("La respuesta del proveedor tiene un formato inesperado.")
    return data


def http_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": "AutoJobAI/0.1 (personal local job search)"})
