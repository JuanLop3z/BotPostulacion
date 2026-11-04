import asyncio
import hashlib
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.dependencies import DB, LocalUser, latest_context, latest_profile, lock_user
from app.core.config import get_settings
from app.core.security import decrypt_document, encrypt_document
from app.models import AuditEvent, CVDocument, ProfileVersion
from app.schemas import CandidateProfile, ContextBundle, Fact
from app.services.cv_parser import parse_cv

router = APIRouter(tags=["candidate"])


def profile_response(profile: ProfileVersion) -> dict[str, Any]:
    return {
        "id": profile.id,
        "version": profile.version,
        "profile": profile.data,
        "reviewed": profile.reviewed,
    }


def add_profile(db: DB, user_id: str, profile: CandidateProfile) -> ProfileVersion:
    previous = latest_profile(db, user_id)
    row = ProfileVersion(
        user_id=user_id,
        version=previous.version + 1 if previous else 1,
        data=profile.model_dump(mode="json"),
        reviewed=profile.reviewed,
    )
    db.add(row)
    db.flush()
    return row


@router.post("/cv", status_code=201)
def upload_cv(file: UploadFile, user: LocalUser, db: DB) -> dict[str, Any]:
    settings = get_settings()
    filename = Path((file.filename or "cv.txt").replace("\\", "/")).name
    content = file.file.read(settings.max_cv_bytes + 1)
    if len(content) > settings.max_cv_bytes:
        raise HTTPException(413, "El CV supera el límite de 10 MB")
    try:
        profile = parse_cv(filename, content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    lock_user(db, user)
    context = ContextBundle.model_validate(latest_context(db, user.id).data)
    if settings.llm_endpoint and context.rules.llm_consent:
        # Explicitly opt-in; the local parser remains available if no LLM is configured.
        from app.services.cv_parser import extract_text
        from app.services.semantic_matching import provider

        try:
            profile = asyncio.run(provider().analyze_cv(extract_text(filename, content), consent=True))
        except (ValueError, RuntimeError):
            raise HTTPException(
                502, "El análisis IA no pudo validarse; desactiva IA o revisa el proveedor"
            ) from None
    profile.reviewed = False
    key = f"{uuid.uuid4()}.enc"
    path = settings.storage_dir / "cv" / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypt_document(content))
    try:
        document = CVDocument(
            user_id=user.id,
            filename=filename,
            storage_key=key,
            sha256=hashlib.sha256(content).hexdigest(),
            size=len(content),
        )
        db.add(document)
        row = add_profile(db, user.id, profile)
        db.add(AuditEvent(user_id=user.id, kind="CV_UPLOADED", message="CV extraído. Revisión pendiente."))
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {**profile_response(row), "document_id": document.id}


@router.get("/cv/{document_id}")
def download_cv(document_id: str, user: LocalUser, db: DB) -> Response:
    document = db.get(CVDocument, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(404, "Documento no encontrado")
    path = get_settings().storage_dir / "cv" / document.storage_key
    if not path.is_file():
        raise HTTPException(404, "Documento eliminado por retención")
    return Response(
        decrypt_document(path.read_bytes()),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="cv-original"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/profile")
def get_profile(user: LocalUser, db: DB) -> dict[str, Any] | None:
    profile = latest_profile(db, user.id)
    return profile_response(profile) if profile else None


class ProfileUpdate(BaseModel):
    profile: CandidateProfile


def record_user_edits(old: CandidateProfile | None, updated: CandidateProfile) -> None:
    """User edits become explicit facts; merely reviewing does not verify an inference."""
    scalar_fields = (
        "full_name",
        "email",
        "phone",
        "location",
        "title",
        "experience_years",
        "seniority",
        "summary",
    )
    for field in scalar_fields:
        value = getattr(updated, field)
        if value not in (None, "") and (old is None or value != getattr(old, field)):
            updated.facts = [fact for fact in updated.facts if fact.field != field]
            updated.facts.append(
                Fact(
                    field=field,
                    value=str(value),
                    source="user",
                    evidence="Edición explícita del usuario",
                    verified=True,
                )
            )
    for field in ("skills", "education", "certifications", "projects"):
        original = getattr(old, field) if old else []
        for value in getattr(updated, field):
            if value not in original:
                updated.facts.append(
                    Fact(
                        field=field,
                        value=value,
                        source="user",
                        evidence="Edición explícita del usuario",
                        verified=True,
                    )
                )
    for language, level in updated.languages.items():
        if old is None or old.languages.get(language) != level:
            updated.facts.append(
                Fact(
                    field=f"languages.{language}",
                    value=level,
                    source="user",
                    evidence="Edición explícita del usuario",
                    verified=True,
                )
            )


@router.put("/profile")
def update_profile(body: ProfileUpdate, user: LocalUser, db: DB) -> dict[str, Any]:
    lock_user(db, user)
    previous = latest_profile(db, user.id)
    profile = body.profile.model_copy(deep=True)
    # Fact provenance cannot be rewritten through the profile editor.
    profile.facts = CandidateProfile.model_validate(previous.data).facts if previous else []
    record_user_edits(CandidateProfile.model_validate(previous.data) if previous else None, profile)
    profile.reviewed = False
    row = add_profile(db, user.id, profile)
    db.commit()
    return profile_response(row)


@router.post("/profile/review")
def review_profile(user: LocalUser, db: DB) -> dict[str, Any]:
    lock_user(db, user)
    previous = latest_profile(db, user.id)
    if previous is None:
        raise HTTPException(409, "Carga o crea primero tu perfil")
    profile = CandidateProfile.model_validate(previous.data)
    profile.reviewed = True
    row = add_profile(db, user.id, profile)
    db.add(AuditEvent(user_id=user.id, kind="PROFILE_REVIEWED", message="Perfil revisado por el usuario."))
    db.commit()
    return profile_response(row)


@router.post("/profile/enrich")
def enrich(user: LocalUser, db: DB) -> dict[str, Any]:
    from app.services.profile_builder import enrich_profile

    lock_user(db, user)
    old = latest_profile(db, user.id)
    if old is None:
        raise HTTPException(409, "Carga o crea primero tu perfil")
    context = ContextBundle.model_validate(latest_context(db, user.id).data)
    profile = enrich_profile(CandidateProfile.model_validate(old.data), context)
    row = add_profile(db, user.id, profile)
    db.commit()
    return profile_response(row)


class VerifyFact(BaseModel):
    field: str
    value: str


@router.post("/profile/verify-fact")
def verify_fact(body: VerifyFact, user: LocalUser, db: DB) -> dict[str, Any]:
    lock_user(db, user)
    old = latest_profile(db, user.id)
    if old is None:
        raise HTTPException(409, "Carga o crea primero tu perfil")
    profile = CandidateProfile.model_validate(old.data)
    found = False
    for fact in profile.facts:
        if fact.field == body.field and fact.value == body.value and not fact.verified:
            fact.evidence = f"Confirmación explícita del usuario; origen: {fact.source}. {fact.evidence}"
            fact.source, fact.verified = "user", True
            found = True
    if not found:
        raise HTTPException(404, "No se encontró ese dato pendiente de verificación")
    profile.reviewed = False
    row = add_profile(db, user.id, profile)
    db.commit()
    return profile_response(row)
