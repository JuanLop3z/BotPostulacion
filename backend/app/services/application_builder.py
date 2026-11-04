from typing import Any

from app.schemas import CandidateProfile, JobData, MatchResult
from app.services.profile_builder import is_verified, verified_skills
from app.services.text_utils import canonical_skill, folded


def build_application(profile: CandidateProfile, job: JobData, match: MatchResult) -> dict[str, Any]:
    """Produce a reviewable draft from confirmed facts, without sending anything."""
    skills = verified_skills(profile)
    job_skills = {folded(canonical_skill(skill)) for skill in job.skills}
    relevant = [skill for skill in skills if folded(skill) in job_skills]
    name = profile.full_name if is_verified(profile, "full_name", profile.full_name) else ""
    title = profile.title if is_verified(profile, "title", profile.title) else ""
    projects = [project for project in profile.projects if is_verified(profile, "projects", project)]
    chosen = [project for project in projects if any(folded(skill) in folded(project) for skill in relevant)][
        :3
    ]
    summary = title or "Perfil profesional pendiente de completar"
    if relevant:
        summary += ". Competencias confirmadas relevantes: " + ", ".join(relevant) + "."
    elif skills:
        summary += ". Competencias confirmadas: " + ", ".join(skills[:12]) + "."
    cover = f"Hola, equipo de {job.company}:\n\nMe interesa la vacante de {job.title}.\n\n{summary}"
    if chosen:
        cover += "\n\nProyectos relevantes:\n" + "\n".join(f"- {project}" for project in chosen)
    cover += "\n\nQuedo disponible para ampliar la información de mi trayectoria."
    if name:
        cover += f"\n\n{name}"
    missing = []
    for field in ("full_name", "email"):
        if not getattr(profile, field) or not is_verified(profile, field, getattr(profile, field)):
            missing.append(f"Confirmar {field} antes de enviar.")
    if not profile.reviewed:
        missing.append("Revisar y confirmar el perfil profesional.")
    pending = list(dict.fromkeys(missing + match.blockers))
    return {
        "summary": summary,
        "cover_letter": cover,
        "answers": {},
        "questions": [{"question": question, "answer": None, "verified": False} for question in pending],
        "pending_questions": pending,
        "selected_projects": chosen,
        "cv_text": _candidate_text(profile),
        "justification": match.decision,
        "facts_used": [{"field": "skills", "value": skill} for skill in relevant],
        "requires_review": True,
        "generation_method": "grounded_template",
    }


def _candidate_text(profile: CandidateProfile) -> str:
    lines = []
    for field in ("full_name", "title", "email", "phone", "location"):
        value = getattr(profile, field)
        if value and is_verified(profile, field, value):
            lines.append(value)
    skills = verified_skills(profile)
    if skills:
        lines.append("Competencias: " + ", ".join(skills))
    experiences = [
        experience.evidence
        for experience in profile.experiences
        if experience.evidence and is_verified(profile, "experiences", experience.evidence)
    ]
    if experiences:
        lines.append("Experiencia:\n" + "\n".join(experiences))
    for field in ("education", "certifications", "projects"):
        verified = [value for value in getattr(profile, field) if is_verified(profile, field, value)]
        if verified:
            lines.append(f"{field}:\n" + "\n".join(verified))
    return "\n\n".join(lines)
