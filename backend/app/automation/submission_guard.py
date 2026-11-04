"""Pure preflight policy. DB locking and idempotency belong to ApplicationManager."""

from typing import Any

from pydantic import BaseModel, Field

from app.integrations.base import JobSourceAdapter
from app.schemas import ApplicationRules, CandidateProfile, JobData, MatchResult


class SubmissionBlocked(ValueError):
    pass


class GuardDecision(BaseModel):
    allowed: bool
    blockers: list[str] = Field(default_factory=list)

    def require_allowed(self) -> None:
        if not self.allowed:
            raise SubmissionBlocked(" ".join(self.blockers))


class SubmissionGuard:
    @staticmethod
    def check(
        *,
        rules: ApplicationRules,
        profile: CandidateProfile,
        job: JobData,
        match: MatchResult,
        adapter: JobSourceAdapter,
        approved: bool,
        daily_count: int,
        weekly_count: int,
        stopped: bool,
        packet: dict[str, Any] | None = None,
        automatic: bool = False,
    ) -> GuardDecision:
        blockers: list[str] = []
        if stopped:
            blockers.append("La parada de automatización está activa.")
        if adapter.name != job.source:
            blockers.append("La fuente de la oferta no corresponde al adaptador de envío.")
        if job.source not in rules.permitted_sources:
            blockers.append("La fuente no está autorizada por el usuario.")
        if not adapter.capabilities.submit:
            blockers.append("La plataforma sólo permite un flujo de postulación manual.")
        if not profile.reviewed:
            blockers.append("Revise y confirme el perfil profesional antes de enviar.")
        if not profile.full_name.strip() or not profile.email.strip():
            blockers.append("Faltan nombre o correo de contacto confirmados.")
        if not match.eligible or match.blockers:
            blockers.append("La vacante tiene requisitos excluyentes pendientes o incumplidos.")
        if match.score < rules.minimum_score:
            blockers.append("La compatibilidad está por debajo del umbral configurado.")
        if rules.mode == "manual":
            blockers.append("El modo manual requiere completar la postulación en el portal.")
        if automatic:
            if rules.mode != "automatic" or not rules.automatic_enabled:
                blockers.append("El usuario no ha habilitado expresamente el envío automático.")
            if rules.requires_approval and not approved:
                blockers.append("Esta candidatura requiere aprobación individual.")
        elif not approved:
            blockers.append("Apruebe la candidatura antes de enviarla.")
        if job.source != "demo" and not rules.third_party_consent:
            blockers.append("Falta consentimiento explícito para compartir datos con terceros.")
        if daily_count >= rules.max_daily:
            blockers.append("Se alcanzó el límite diario de postulaciones.")
        if weekly_count >= rules.max_weekly:
            blockers.append("Se alcanzó el límite semanal de postulaciones.")
        if packet is not None:
            if packet.get("pending_questions"):
                blockers.append("Hay preguntas sin respuesta validada.")
            if packet.get("unverified_fields"):
                blockers.append("La candidatura contiene información no verificada.")
            questions = packet.get("questions", [])
            if isinstance(questions, list) and any(
                isinstance(question, dict)
                and question.get("answer") is not None
                and question.get("verified") is not True
                for question in questions
            ):
                blockers.append("Existen respuestas de selección sin verificar.")
            answers = packet.get("answers", {})
            if isinstance(answers, dict) and any(
                not isinstance(answer, dict) or answer.get("verified") is not True
                for answer in answers.values()
            ):
                blockers.append("Cada respuesta debe tener una verificación explícita.")
        return GuardDecision(allowed=not blockers, blockers=blockers)
