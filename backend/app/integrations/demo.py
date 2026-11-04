"""Offline sandbox only. No emails, employers, or external services are contacted."""

import hashlib
from typing import Any

from app.integrations.base import JobSourceAdapter, SourceCapabilities, SourceError, SubmissionResult
from app.schemas import JobData


class DemoAdapter(JobSourceAdapter):
    name = "demo"
    label = "Proveedor de pruebas local"
    description = "Vacantes ficticias y envío de prueba sin terceros. Nunca cuenta como postulación real."
    capabilities = SourceCapabilities(details=True, requirements=True, salary=True, submit=True, status=True)
    minimum_refresh_hours = 0

    def search(self, query: str = "", board: str | None = None) -> list[JobData]:
        jobs = [
            JobData(
                source="demo",
                external_id="demo-python-backend",
                title="[PRUEBA] Backend Developer · Python",
                company="Empresa ficticia · Sandbox",
                url="https://example.invalid/demo/python-backend",
                description=(
                    "Vacante ficticia para probar el flujo local. Desarrollo de APIs con Python, "
                    "FastAPI y PostgreSQL. No existe empleador ni se envían datos fuera del sistema."
                ),
                location="Worldwide",
                work_mode="remote",
                skills=["Python", "FastAPI", "PostgreSQL"],
                contract_type="full_time",
            ),
            JobData(
                source="demo",
                external_id="demo-ml-license",
                title="[PRUEBA] Machine Learning Engineer",
                company="Laboratorio ficticio · Sandbox",
                url="https://example.invalid/demo/ml-engineer",
                description="Vacante ficticia con requisito excluyente para demostrar el bloqueo de elegibilidad.",
                location="Worldwide",
                work_mode="remote",
                skills=["Python", "TensorFlow", "Kubernetes"],
                mandatory_requirements=["Licencia profesional de ingeniería vigente"],
            ),
            JobData(
                source="demo",
                external_id="demo-fullstack",
                title="[PRUEBA] Full Stack Developer",
                company="Estudio ficticio · Sandbox",
                url="https://example.invalid/demo/fullstack",
                description="Vacante ficticia: Python, React y TypeScript. Únicamente para la demostración local.",
                location="Worldwide",
                work_mode="remote",
                skills=["Python", "React", "TypeScript"],
            ),
        ]
        if query.strip():
            needle = query.strip().casefold()
            jobs = [
                job for job in jobs if needle in f"{job.title} {job.company} {job.description}".casefold()
            ]
        return jobs

    def details(self, external_id: str, board: str | None = None) -> JobData:
        for job in self.search():
            if job.external_id == external_id:
                return job
        raise SourceError("La vacante de prueba no existe.")

    def submit(self, application_id: str, packet: dict[str, Any]) -> SubmissionResult:
        if not application_id or len(application_id) > 200:
            raise SourceError("Identificador de candidatura de prueba inválido.")
        # A separate adapter capability check and DB uniqueness guard are required
        # by ApplicationManager before this method. Deterministic IDs preserve
        # idempotency even after a process restart.
        source = packet.get("source")
        if source is not None and source != "demo":
            raise SourceError("El sandbox sólo acepta candidaturas con origen demo.")
        pending = packet.get("pending_questions") or []
        if pending:
            raise SourceError("La candidatura contiene preguntas pendientes.", requires_human=True)
        digest = hashlib.sha256(f"autojob-demo:{application_id}".encode()).hexdigest()[:24]
        reference = f"DEMO-{digest}"
        return self.status(reference)

    def status(self, reference: str) -> SubmissionResult:
        if not reference.startswith("DEMO-") or len(reference) != 29:
            raise SourceError("Referencia de prueba inválida.")
        return SubmissionResult(
            submitted=True,
            confirmed=True,
            reference=reference,
            evidence={
                "provider": "demo",
                "simulation": True,
                "reference": reference,
                "transport": "in_process",
                "message": "Recepción confirmada sólo en sandbox local. No es una postulación real.",
            },
        )
