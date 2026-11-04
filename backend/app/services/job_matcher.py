"""Explainable weighted matching with eligibility evaluated independently."""

import re

from app.schemas import CandidateProfile, ContextBundle, JobData, MatchResult
from app.services.profile_builder import is_verified, verified_skills
from app.services.text_utils import (
    SKILL_ALIASES,
    canonical_skill,
    contains_term,
    extract_skills,
    folded,
    language_levels,
)

_LEVELS = {
    "a1": 1,
    "a2": 2,
    "b1": 3,
    "b2": 4,
    "c1": 5,
    "c2": 6,
    "basic": 2,
    "basico": 2,
    "intermediate": 3,
    "intermedio": 3,
    "advanced": 5,
    "avanzado": 5,
    "fluent": 5,
    "native": 6,
    "nativo": 6,
    "nativa": 6,
}
_SENIORITY = {
    "intern": 0,
    "junior": 1,
    "jr": 1,
    "mid": 2,
    "middle": 2,
    "semi senior": 2,
    "senior": 3,
    "sr": 3,
    "lead": 4,
    "principal": 4,
}


def _rank(value: str) -> int:
    return _LEVELS.get(folded(value), 0)


def _language_met(profile: CandidateProfile, language: str, required: str) -> bool:
    actual = profile.languages.get(language, "")
    return (
        bool(actual)
        and is_verified(profile, f"languages.{language}", actual)
        and (_rank(actual) >= _rank(required) > 0)
    )


def _mandatory_met(profile: CandidateProfile, requirement: str, skills: set[str]) -> bool:
    """Fail closed for unmodelled legal, licence, migration and free-form obligations."""
    requirement_folded = folded(requirement)
    if re.search(
        r"\b(visa|citizenship|citizen|work authorization|authorized to work|"
        r"security clearance|autorizacion|permiso|ciudadania)\b",
        requirement_folded,
    ):
        return False
    if re.search(
        r"\b(licencia|license|licence|certification|certificacion|certified|degree|"
        r"titulo universitario)\b",
        requirement_folded,
    ):
        for field, collection in (
            ("certifications", profile.certifications),
            ("education", profile.education),
        ):
            for item in collection:
                if is_verified(profile, field, item) and folded(item) in requirement_folded:
                    remaining = requirement_folded.replace(folded(item), " ")
                    if _only_filler(remaining):
                        return True
        return False
    known_skills = {folded(canonical_skill(value)) for value in extract_skills(requirement)}
    languages = language_levels(requirement)
    years = re.search(r"\b(\d{1,2}(?:[.,]\d)?)\s*\+?\s*(?:years|años)\b", requirement, re.I)
    any_known = bool(known_skills or languages or years)
    if known_skills and not known_skills.issubset(skills):
        return False
    if any(not _language_met(profile, language, level) for language, level in languages.items()):
        return False
    if years:
        if (
            profile.experience_years is None
            or not is_verified(profile, "experience_years", str(profile.experience_years))
            or profile.experience_years < float(years.group(1).replace(",", "."))
        ):
            return False
    remainder = requirement_folded
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in (canonical, *aliases):
            remainder = re.sub(r"(?<![\w])" + re.escape(folded(alias)) + r"(?![\w])", " ", remainder)
    remainder = re.sub(r"\b\d{1,2}(?:[.,]\d)?\s*\+?\s*(?:years|anos)\b", " ", remainder)
    for language in languages:
        for alias in {
            "english": ("english", "ingles"),
            "spanish": ("spanish", "espanol"),
            "portuguese": ("portuguese", "portugues"),
            "french": ("french", "frances"),
            "german": ("german", "aleman"),
        }.get(language, (language,)):
            remainder = re.sub(r"\b" + alias + r"\b", " ", remainder)
    remainder = re.sub(
        r"\b(?:a1|a2|b1|b2|c1|c2|native|nativo|nativa|basic|basico|intermediate|"
        r"intermedio|advanced|avanzado|fluent)\b",
        " ",
        remainder,
    )
    return any_known and _only_filler(remainder)


def _only_filler(value: str) -> bool:
    """Unknown conjuncts stay pending instead of being verified by a nearby known skill."""
    filler = {
        "must",
        "have",
        "has",
        "required",
        "mandatory",
        "requirement",
        "requirements",
        "minimum",
        "at",
        "least",
        "experience",
        "with",
        "in",
        "of",
        "and",
        "or",
        "a",
        "an",
        "the",
        "is",
        "be",
        "are",
        "proficiency",
        "proficient",
        "knowledge",
        "strong",
        "solid",
        "programming",
        "development",
        "skills",
        "skill",
        "working",
        "professional",
        "technical",
        "nivel",
        "idioma",
        "language",
        "level",
        "de",
        "la",
        "el",
        "los",
        "las",
        "un",
        "una",
        "y",
        "o",
        "con",
        "en",
        "es",
        "son",
        "se",
        "requiere",
        "requieren",
        "tener",
        "debe",
        "deben",
        "contar",
        "experiencia",
        "conocimiento",
        "conocimientos",
        "dominio",
        "obligatorio",
        "obligatoria",
        "indispensable",
        "excluyente",
        "minimo",
        "minima",
        "requerido",
        "requerida",
        "desarrollo",
        "programacion",
        "habilidades",
    }
    return all(token in filler for token in re.findall(r"[a-z0-9]+", value))


def match_job(
    profile: CandidateProfile,
    job: JobData,
    context: ContextBundle,
    *,
    semantic_similarity: float | None = None,
) -> MatchResult:
    prefs, rules = context.preferences, context.rules
    matches: list[str] = []
    gaps: list[str] = []
    blockers: list[str] = []
    salary_review_reason: str | None = None
    candidate_skills = {folded(canonical_skill(skill)) for skill in verified_skills(profile)}
    required_skills = {folded(canonical_skill(skill)) for skill in job.skills}
    shared = candidate_skills & required_skills
    matches.extend(skill for skill in job.skills if folded(canonical_skill(skill)) in shared)
    gaps.extend(
        f"Competencia por verificar: {skill}"
        for skill in job.skills
        if folded(canonical_skill(skill)) not in candidate_skills
    )
    technical = len(shared) / len(required_skills) * 100 if required_skills else 50.0
    method = "rules_keywords"
    if semantic_similarity is not None:
        # Semantic similarity refines the ranking; it never changes a hard eligibility result.
        technical = technical * 0.8 + max(0.0, min(1.0, semantic_similarity)) * 20
        method = "rules_keywords_embeddings"
    experience = 50.0
    if job.minimum_years is not None:
        verified_years = profile.experience_years is not None and is_verified(
            profile, "experience_years", str(profile.experience_years)
        )
        if not verified_years:
            experience = 0
            blockers.append("Años de experiencia requeridos sin verificar.")
        elif profile.experience_years is not None:
            experience = min(100, profile.experience_years / max(job.minimum_years, 0.1) * 100)
            if profile.experience_years < job.minimum_years:
                blockers.append(f"Requiere al menos {job.minimum_years:g} años de experiencia.")
            else:
                matches.append("Experiencia mínima acreditada en el perfil.")
    seniority = 50.0
    if job.seniority:
        if profile.seniority and is_verified(profile, "seniority", profile.seniority):
            candidate_rank = _SENIORITY.get(folded(profile.seniority))
            job_rank = _SENIORITY.get(folded(job.seniority))
            if candidate_rank is not None and job_rank is not None:
                seniority = max(0, 100 - abs(candidate_rank - job_rank) * 35)
        else:
            gaps.append("Seniority sin verificar.")
    preference_checks: list[bool] = []
    if prefs.work_modes and job.work_mode != "unknown":
        accepted = job.work_mode in prefs.work_modes
        preference_checks.append(accepted)
        if not accepted:
            blockers.append(f"Modalidad excluida: {job.work_mode}.")
    elif prefs.work_modes and job.work_mode == "unknown":
        gaps.append("Modalidad laboral no publicada.")
    if prefs.countries or prefs.cities:
        location = folded(job.location)
        worldwide = any(term in location for term in ("worldwide", "anywhere", "global", "todo el mundo"))
        accepted = (worldwide and job.work_mode == "remote") or any(
            folded(place) in location for place in prefs.countries + prefs.cities
        )
        preference_checks.append(accepted)
        if not accepted:
            blockers.append("La ubicación no coincide con los países o ciudades configurados.")
    if prefs.contract_types and job.contract_type:
        accepted = folded(job.contract_type) in {folded(kind) for kind in prefs.contract_types}
        preference_checks.append(accepted)
        if not accepted:
            blockers.append("Tipo de contrato excluido.")
    if prefs.preferred_cities and job.location and job.work_mode != "remote":
        preferred = any(contains_term(job.location, city) for city in prefs.preferred_cities)
        preference_checks.append(preferred)
        if preferred:
            matches.append("Ubicación en una ciudad preferida.")
        else:
            gaps.append("Ciudad distinta de las preferidas; considerar movilidad.")
    if prefs.preferred_contract_types:
        # Hours (full_time) do not establish whether a contract is indefinite.
        aliases = {
            "permanent": "indefinido",
            "termino indefinido": "indefinido",
            "indefinido": "indefinido",
            "open_ended": "indefinido",
            "contract": "contractor",
            "contractor": "contractor",
            "freelance": "freelance",
            "fixed_term": "temporal",
            "termino fijo": "temporal",
            "temporal": "temporal",
            "prestacion de servicios": "contractor",
        }
        kind = aliases.get(folded(job.contract_type))
        desired = {aliases.get(folded(value), folded(value)) for value in prefs.preferred_contract_types}
        if kind is not None:
            preferred = kind in desired
            preference_checks.append(preferred)
            if preferred:
                matches.append("Tipo de contrato preferido.")
            else:
                gaps.append("Contrato alternativo; revisar compensación y condiciones.")
        else:
            gaps.append("Duración o naturaleza del contrato por confirmar.")
    if prefs.seniority and job.seniority:
        accepted = folded(job.seniority) in {folded(level) for level in prefs.seniority}
        preference_checks.append(accepted)
        if not accepted:
            blockers.append("Seniority fuera de las preferencias.")
    if any(folded(company) == folded(job.company) for company in prefs.excluded_companies):
        blockers.append("Empresa excluida por tus preferencias.")
    if any(contains_term(job.title, term) for term in prefs.excluded_titles):
        blockers.append("Cargo excluido por tus preferencias.")
    if any(contains_term(job.title + "\n" + job.description, term) for term in prefs.negative_keywords):
        blockers.append("La oferta contiene palabras clave excluidas.")
    if any(folded(canonical_skill(skill)) in required_skills for skill in prefs.excluded_technologies):
        blockers.append("La oferta requiere una tecnología excluida.")
    if prefs.target_roles:
        preference_checks.append(any(contains_term(job.title, role) for role in prefs.target_roles))
    if prefs.preferred_stack:
        preference_checks.append(
            bool({folded(canonical_skill(skill)) for skill in prefs.preferred_stack} & required_skills)
        )
    if prefs.positive_keywords:
        preference_checks.append(
            any(contains_term(job.title + " " + job.description, term) for term in prefs.positive_keywords)
        )
    preferences = sum(preference_checks) / len(preference_checks) * 100 if preference_checks else 100.0
    salary = 50.0
    if prefs.minimum_monthly is not None:
        if (
            job.salary_max is None
            or job.currency != prefs.currency
            or job.salary_period not in {"month", "year"}
        ):
            gaps.append("Salario no comparable; confirmar monto, moneda y periodicidad.")
            blockers.append("No se puede verificar el salario mínimo configurado.")
        else:
            monthly_max = job.salary_max / (12 if job.salary_period == "year" else 1)
            salary_target = max(prefs.minimum_monthly, prefs.desired_monthly or 0)
            salary = min(100, monthly_max / max(salary_target, 1) * 100)
            if monthly_max < prefs.minimum_monthly:
                if prefs.salary_below_minimum_requires_review:
                    salary_review_reason = "Salario inferior al mínimo: revisar individualmente el plan de incrementos antes de aceptar."
                    gaps.append(salary_review_reason)
                else:
                    blockers.append("El salario publicado es inferior al mínimo configurado.")
            elif job.salary_min is not None:
                monthly_min = job.salary_min / (12 if job.salary_period == "year" else 1)
                if monthly_min < prefs.minimum_monthly:
                    gaps.append("El rango salarial cruza tu mínimo; confirmar la oferta económica.")
    languages = 100.0 if not job.languages else 0.0
    if job.languages:
        met = sum(_language_met(profile, language, level) for language, level in job.languages.items())
        languages = met / len(job.languages) * 100
        for language, level in job.languages.items():
            if not _language_met(profile, language, level):
                blockers.append(f"Idioma requerido por verificar: {language} {level}.")
    for language, level in prefs.required_languages.items():
        if not _language_met(profile, language, level):
            blockers.append(f"Nivel de idioma configurado sin verificar: {language} {level}.")
    custom = folded(context.custom_instructions)
    if ("ingles c1" in custom or "english c1" in custom) and re.search(r"\b(no|evitar|avoid)\b", custom):
        if _rank(job.languages.get("english", "")) >= _rank("C1"):
            blockers.append("La instrucción personal excluye ofertas con inglés C1 o superior.")
    for requirement in job.mandatory_requirements:
        if not _mandatory_met(profile, requirement, candidate_skills):
            blockers.append(f"Requisito obligatorio pendiente: {requirement}")
    if not profile.reviewed:
        blockers.append("El perfil necesita revisión y confirmación del usuario.")
    breakdown = {
        "technical": technical,
        "experience": experience,
        "seniority": seniority,
        "preferences": preferences,
        "salary": salary,
        "languages": languages,
    }
    denominator = sum(rules.matching_weights.values())
    score = round(
        sum(breakdown[key] * weight for key, weight in rules.matching_weights.items()) / denominator, 1
    )
    if score < rules.minimum_score:
        blockers.append(f"Compatibilidad inferior al umbral de {rules.minimum_score:g}.")
    requires_human_review = salary_review_reason is not None and not blockers
    if salary_review_reason is not None:
        blockers.append(salary_review_reason)
    blockers = list(dict.fromkeys(blockers))
    eligible = not blockers
    decision = "Postulación recomendada." if eligible else "Requiere revisión o no cumple las reglas."
    if requires_human_review:
        decision = "Revisión humana requerida para valorar los incrementos salariales."
    return MatchResult(
        score=score,
        eligible=eligible,
        decision=decision,
        matches=matches,
        gaps=gaps,
        blockers=blockers,
        breakdown={key: round(value, 1) for key, value in breakdown.items()},
        method=method,
        requires_human_review=requires_human_review,
    )
