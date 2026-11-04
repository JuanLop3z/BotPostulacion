import re

from app.schemas import CandidateProfile, ContextBundle, Fact
from app.services.text_utils import canonical_skill, folded


def verified_skills(profile: CandidateProfile) -> list[str]:
    if not profile.reviewed:
        return []
    result = []
    for skill in profile.skills:
        facts = [
            fact
            for fact in profile.facts
            if fact.field == "skills"
            and folded(canonical_skill(fact.value)) == folded(canonical_skill(skill))
        ]
        if any(fact.verified and fact.source in {"cv", "context", "user"} for fact in facts):
            result.append(canonical_skill(skill))
    return sorted(set(result))


def is_verified(profile: CandidateProfile, field: str, value: str) -> bool:
    return profile.reviewed and any(
        fact.field == field
        and folded(fact.value) == folded(value)
        and fact.verified
        and fact.source in {"cv", "context", "user"}
        for fact in profile.facts
    )


def enrich_profile(profile: CandidateProfile, context: ContextBundle) -> CandidateProfile:
    """Only labelled context assertions are proposed; private prose is never copied out."""
    enriched = profile.model_copy(deep=True)
    private_section = False
    for line in context.candidate_context.splitlines():
        normalized = folded(line.strip())
        private_marker = any(
            marker in normalized
            for marker in (
                "no compartir",
                "no debe compartirse",
                "informacion privada",
                "informacion confidencial",
                "private",
                "do not share",
                "privado:",
                "confidencial:",
            )
        )
        if line.lstrip().startswith("#"):
            private_section = private_marker
        elif private_marker:
            private_section = True
        if private_section:
            continue
        match = re.match(
            r"\s*(?:habilidades confirmadas|tecnologías confirmadas|tecnologias confirmadas|"
            r"verified skills|confirmed skills|skills|habilidades|tecnologías|tecnologias)\s*:\s*(.+)",
            line,
            re.IGNORECASE,
        )
        if match:
            for item in re.split(r"[,;]", match.group(1)):
                skill = canonical_skill(item)
                if skill and skill not in enriched.skills:
                    enriched.skills.append(skill)
                    enriched.facts.append(
                        Fact(
                            field="skills",
                            value=skill,
                            source="context",
                            evidence=line.strip(),
                            verified=False,
                        )
                    )
        years = re.match(
            r"\s*(?:años de experiencia|anos de experiencia|experience_years|"
            r"experiencia confirmada)\s*:\s*(\d{1,2}(?:[.,]\d)?)\s*(?:años|years)?\s*$",
            line,
            re.IGNORECASE,
        )
        if years and enriched.experience_years is None:
            enriched.experience_years = float(years.group(1).replace(",", "."))
            enriched.facts.append(
                Fact(
                    field="experience_years",
                    value=str(enriched.experience_years),
                    source="context",
                    evidence=line.strip(),
                    verified=False,
                )
            )
    if enriched.skills != profile.skills or enriched.experience_years != profile.experience_years:
        enriched.reviewed = False
    return enriched
