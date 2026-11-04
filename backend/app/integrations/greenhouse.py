"""Read-only Greenhouse Job Board API. Employer-owned API keys are not assumed.

Reference: https://docs.greenhouse.io/job-board.html
"""

import re
from typing import Any, Literal

import httpx

from app.integrations._common import http_client, json_response, plain_text, publication_date, safe_job_url
from app.integrations.base import JobSourceAdapter, SourceCapabilities, SourceError
from app.schemas import JobData


class GreenhouseAdapter(JobSourceAdapter):
    name = "greenhouse"
    label = "Greenhouse"
    description = "Job Board API pública · indique el token del portal de una empresa; envío manual."
    capabilities = SourceCapabilities(details=True, requirements=True, salary=True)
    endpoint = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    @staticmethod
    def _board(board: str | None) -> str:
        if not board or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", board):
            raise SourceError("Indique un token Greenhouse válido (letras, números, guiones).")
        return board

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._client:
            return json_response(self._client, url, params)
        with http_client() as client:
            return json_response(client, url, params)

    def search(self, query: str = "", board: str | None = None) -> list[JobData]:
        token = self._board(board)
        data = self._get(f"{self.endpoint}/{token}/jobs", {"content": "true"})
        records = data.get("jobs")
        if not isinstance(records, list):
            raise SourceError("Greenhouse cambió el formato de su listado de vacantes.")
        jobs = [self._normalize(record, token) for record in records if isinstance(record, dict)]
        if query.strip():
            needle = query.strip().casefold()
            jobs = [
                job for job in jobs if needle in f"{job.title} {job.company} {job.description}".casefold()
            ]
        return jobs

    def details(self, external_id: str, board: str | None = None) -> JobData:
        if ":" in external_id and board is None:
            board, external_id = external_id.split(":", 1)
        token = self._board(board)
        if not re.fullmatch(r"\d{1,20}", external_id):
            raise SourceError("Identificador Greenhouse inválido.")
        record = self._get(
            f"{self.endpoint}/{token}/jobs/{external_id}",
            {"questions": "true", "pay_transparency": "true"},
        )
        return self._normalize(record, token)

    def _normalize(self, record: dict[str, Any], board: str) -> JobData:
        external_id = str(record.get("id", ""))
        if not external_id or not record.get("title"):
            raise SourceError("Greenhouse devolvió una vacante sin identificador o título.")
        location_data = record.get("location")
        location = plain_text(location_data.get("name")) if isinstance(location_data, dict) else ""
        lower_location = location.casefold()
        work_mode: Literal["remote", "hybrid", "onsite", "unknown"] = (
            "remote" if "remote" in lower_location else "hybrid" if "hybrid" in lower_location else "unknown"
        )
        return JobData(
            source=self.name,
            # IDs are unique within a board; prefix it to avoid cross-company collisions.
            external_id=f"{board}:{external_id}",
            title=plain_text(record.get("title")),
            company=plain_text(record.get("company_name")) or board,
            url=safe_job_url(
                record.get("absolute_url"),
                fallback=f"https://boards.greenhouse.io/{board}/jobs/{external_id}",
            ),
            description=plain_text(record.get("content")),
            location=location,
            work_mode=work_mode,
            # updated_at is not necessarily the publication date.
            published_at=publication_date(record.get("first_published")),
        )
