"""Opt-in, real provider embeddings, cached per account without storing source text."""

import asyncio
import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmbeddingCache
from app.schemas import CandidateProfile, JobData
from app.services.ai_provider import StructuredHTTPProvider, cosine_similarity
from app.services.profile_builder import verified_skills


def provider() -> Any:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        from app.services.ai_provider import OllamaProvider

        return OllamaProvider(
            settings.llm_endpoint,
            model=settings.llm_model or "llama3.2",
            embedding_model=settings.embedding_model,
            api_key=settings.llm_api_key,
        )
    return StructuredHTTPProvider(settings.llm_endpoint, settings.llm_api_key)


def engine_key(consent: bool) -> str:
    settings = get_settings()
    enabled = settings.enable_embeddings and consent and bool(settings.llm_endpoint)
    value = f"rules-v1:{enabled}:{settings.llm_provider}:{settings.llm_endpoint}:{settings.embedding_model}"
    return hashlib.sha256(value.encode()).hexdigest()


def cached_embedding(db: Session, user_id: str, text: str) -> EmbeddingCache:
    settings = get_settings()
    key = hashlib.sha256(f"{engine_key(True)}:{text}".encode()).hexdigest()
    row = db.scalar(
        select(EmbeddingCache).where(EmbeddingCache.user_id == user_id, EmbeddingCache.cache_key == key)
    )
    if row:
        return row
    values = asyncio.run(provider().embed(text[:20000], consent=True))
    row = EmbeddingCache(user_id=user_id, cache_key=key, model=settings.embedding_model, vector=values)
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        row = db.execute(
            select(EmbeddingCache).where(EmbeddingCache.user_id == user_id, EmbeddingCache.cache_key == key)
        ).scalar_one()
    return row


def similarity(
    db: Session, user_id: str, profile: CandidateProfile, job: JobData, *, consent: bool
) -> float | None:
    settings = get_settings()
    if not settings.enable_embeddings or not settings.llm_endpoint or not consent or not profile.reviewed:
        return None
    # No personal contact details or free-text private context are needed for matching.
    candidate_text = "Competencias verificadas: " + ", ".join(verified_skills(profile))
    job_text = f"{job.title}\n{', '.join(job.skills)}\n{job.description}"
    candidate = cached_embedding(db, user_id, candidate_text)
    vacancy = cached_embedding(db, user_id, job_text)
    if len(candidate.vector) != len(vacancy.vector):
        raise ValueError("Las dimensiones de embeddings cambiaron; revisa el modelo configurado")
    if db.get_bind().dialect.name == "postgresql":
        distance = db.scalar(
            select(EmbeddingCache.vector.cosine_distance(candidate.vector)).where(
                EmbeddingCache.id == vacancy.id
            )
        )
        return 1 - float(distance) if distance is not None else None
    return cosine_similarity(candidate.vector, vacancy.vector)
