"""Remotive's documented public read-only feed, with mandatory source attribution.

Reference: https://github.com/remotive-com/remote-jobs-api
The orchestration layer must cache this feed for at least six hours globally.
"""

from typing import Any

import httpx

from app.integrations._common import http_client, json_response, plain_text, publication_date, safe_job_url
from app.integrations.base import JobSourceAdapter, SourceCapabilities, SourceError
from app.schemas import JobData


class RemotiveAdapter(JobSourceAdapter):
    name = "remotive"
    label = "Remotive"
    description = "API pública de Remotive · búsqueda y lectura; postulación manual en el enlace original."
    capabilities = SourceCapabilities(requirements=True, salary=True)
    endpoint = "https://remotive.com/api/remote-jobs"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def search(self, query: str = "", board: str | None = None) -> list[JobData]:
        # Request the full feed once; different user queries are filtered locally by the
        # service so they cannot multiply the provider's four recommended daily requests.
        if self._client:
            data = json_response(self._client, self.endpoint, {})
        else:
            with http_client() as client:
                data = json_response(client, self.endpoint, {})
        records = data.get("jobs")
        if not isinstance(records, list):
            raise SourceError("Remotive cambió el formato de su listado de vacantes.")
        jobs = [self._normalize(record) for record in records if isinstance(record, dict)]
        if query.strip():
            needle = query.casefold().strip()
            jobs = [
                job for job in jobs if needle in f"{job.title} {job.company} {job.description}".casefold()
            ]
        return jobs

    def _normalize(self, record: dict[str, Any]) -> JobData:
        external_id = str(record.get("id", ""))
        if not external_id or not record.get("title"):
            raise SourceError("Remotive devolvió una vacante sin identificador o título.")
        description = plain_text(record.get("description"))
        salary_text = plain_text(record.get("salary"))
        if salary_text:
            description = f"{description}\n\nSalario publicado por Remotive (sin normalizar): {salary_text}"
        tags = record.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        return JobData(
            source=self.name,
            external_id=external_id,
            title=plain_text(record.get("title")),
            company=plain_text(record.get("company_name")) or "Empresa no informada",
            url=safe_job_url(record.get("url"), fallback="https://remotive.com/remote-jobs"),
            description=description,
            location=plain_text(record.get("candidate_required_location")),
            work_mode="remote",
            skills=[plain_text(tag) for tag in tags if isinstance(tag, str)],
            contract_type=str(record.get("job_type") or "unknown"),
            published_at=publication_date(record.get("publication_date")),
            # Remotive's free-text salary can mix currencies/periods. Leave numeric
            # values unknown rather than invent a salary or an exchange rate.
        )
