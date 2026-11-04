"""Import pasted data without portal access. Matching honors the configured AI consent."""

import hashlib
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit, urlunsplit

from fastapi import HTTPException
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import latest_context, latest_profile, lock_user
from app.models import Application, AuditEvent, Evaluation, Job, User
from app.schemas import JobData
from app.schemas.job_import import AssistedJobImport
from app.services.job_normalizer import canonical_url, job_fingerprint, normalize_job
from app.services.search_pipeline import evaluate_job


def source_identity(body: AssistedJobImport) -> tuple[str, str]:
    parts = urlsplit(body.url)
    if body.source == "linkedin":
        match = re.fullmatch(r"/jobs/view/(?:[^/]*-)?(\d{1,20})/?", parts.path)
        native_id = match.group(1) if match else parse_qs(parts.query).get("currentJobId", [""])[0]
        if not re.fullmatch(r"\d{1,20}", native_id) or not parts.path.startswith("/jobs/"):
            raise ValueError("Pega el enlace de una vacante concreta de LinkedIn, no el de un perfil")
        return native_id, f"https://www.linkedin.com/jobs/view/{native_id}"
    cleaned = canonical_url(body.url)
    # A tracking query never turns the same portal vacancy into a second application.
    if body.source == "computrabajo":
        cleaned = urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))
    return hashlib.sha256(cleaned.encode()).hexdigest(), cleaned


def serialize_imported_job(db: Session, owner: User, job: Job) -> dict[str, Any]:
    profile = latest_profile(db, owner.id)
    context = latest_context(db, owner.id)
    evaluation = evaluate_job(db, owner.id, job, profile, context) if profile else None
    application_state = db.scalar(
        select(Application.state).where(Application.user_id == owner.id, Application.job_id == job.id)
    )
    return {
        "id": job.id,
        **job.data,
        "match": evaluation.data if evaluation else None,
        "application_state": application_state,
    }


def import_assisted_job(db: Session, owner: User, body: AssistedJobImport) -> dict[str, Any]:
    lock_user(db, owner)
    external_id, url = source_identity(body)
    data = body.model_dump(exclude={"url"})
    vacancy = normalize_job(JobData(**data, url=url, external_id=external_id, ingestion_method="assisted"))
    if not vacancy.title.strip() or not vacancy.company.strip() or len(vacancy.description.strip()) < 20:
        raise ValueError("El título, la empresa y el texto deben contener información visible suficiente")
    fingerprint = job_fingerprint(vacancy)
    identity = (
        Job.user_id == owner.id,
        or_(
            Job.fingerprint == fingerprint,
            and_(Job.source == vacancy.source, Job.external_id == vacancy.external_id),
            Job.data["url"].as_string() == vacancy.url,
        ),
    )
    existing = db.scalar(select(Job).where(*identity))
    duplicate = existing is not None
    if existing is None:
        row = Job(
            user_id=owner.id,
            fingerprint=fingerprint,
            source=vacancy.source,
            external_id=vacancy.external_id,
            data=vacancy.model_dump(mode="json"),
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
            existing = row
        except IntegrityError:
            existing = db.execute(select(Job).where(*identity)).scalar_one()
            duplicate = True
    result = serialize_imported_job(db, owner, existing)
    db.add(
        AuditEvent(
            user_id=owner.id,
            kind="JOB_IMPORT_DUPLICATE" if duplicate else "JOB_IMPORTED",
            message="Oferta ya registrada; se conserva la versión anterior."
            if duplicate
            else "Oferta importada desde texto aportado por el usuario; postulación manual.",
            details={"job_id": existing.id, "source": existing.source},
        )
    )
    db.commit()
    message = "Oferta importada y analizada. El envío se realiza en el portal original."
    if result["match"] is None:
        message = "Oferta importada. Completa tu perfil para analizar la compatibilidad."
    if duplicate:
        message = "Esta oferta ya estaba registrada; se muestra la versión guardada."
    return {
        "job": result,
        "duplicate": duplicate,
        "message": message,
    }


def update_assisted_job(db: Session, owner: User, job_id: str, body: AssistedJobImport) -> dict[str, Any]:
    lock_user(db, owner)
    row = db.scalar(select(Job).where(Job.user_id == owner.id, Job.id == job_id))
    if row is None:
        raise HTTPException(404, "Oferta no encontrada")
    if row.data.get("ingestion_method") != "assisted":
        raise HTTPException(409, "Sólo se pueden completar ofertas importadas por ti")
    external_id, url = source_identity(body)
    if body.source != row.source or external_id != row.external_id:
        raise HTTPException(409, "Para otra oferta o portal, crea una nueva importación")
    application = db.scalar(
        select(Application).where(Application.user_id == owner.id, Application.job_id == row.id)
    )
    if application and application.state in {"SUBMITTED", "CONFIRMED", "WITHDRAWN", "SKIPPED"}:
        raise HTTPException(409, "Se conserva la oferta de una candidatura ya registrada como definitiva")
    vacancy = normalize_job(
        JobData(
            **body.model_dump(exclude={"url"}), url=url, external_id=external_id, ingestion_method="assisted"
        )
    )
    if not vacancy.title.strip() or not vacancy.company.strip() or len(vacancy.description.strip()) < 20:
        raise ValueError("El título, la empresa y el texto deben contener información visible suficiente")
    fingerprint = job_fingerprint(vacancy)
    other = db.scalar(
        select(Job.id).where(Job.user_id == owner.id, Job.id != row.id, Job.fingerprint == fingerprint)
    )
    if other:
        raise HTTPException(409, "Estos datos corresponden a otra oferta ya registrada")
    if application:
        from app.services.application_manager import transition

        application.approved = False
        if application.state in {"PREPARED", "PENDING_APPROVAL"}:
            transition(
                db, application, "NEEDS_INFORMATION", "La oferta cambió; regenera y revisa la candidatura."
            )
    row.data, row.fingerprint = vacancy.model_dump(mode="json"), fingerprint
    db.execute(delete(Evaluation).where(Evaluation.user_id == owner.id, Evaluation.job_id == row.id))
    result = serialize_imported_job(db, owner, row)
    db.add(
        AuditEvent(
            user_id=owner.id,
            kind="JOB_IMPORT_UPDATED",
            message="Datos de oferta importada completados; compatibilidad recalculada.",
            details={"job_id": row.id, "source": row.source},
        )
    )
    db.commit()
    return {
        "job": result,
        "duplicate": False,
        "message": "Oferta actualizada y analizada. Regenera las candidaturas preparadas antes de continuar.",
    }
