import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.schemas import JobData
from app.services.text_utils import canonical_skill, extract_skills, folded, language_levels, plain_text


def canonical_url(value: str) -> str:
    parts = urlsplit(value)
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in {"ref", "source", "referral", "trk", "trackingid", "gh_src"}
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(sorted(query)), "")
    )


def _identity(value: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", folded(value)).strip()


def job_fingerprint(job: JobData) -> str:
    """A conservative cross-board identity, independent of tracking links or board IDs."""
    identity = "|".join(_identity(value) for value in (job.company, job.title, job.location))
    return hashlib.sha256(identity.encode()).hexdigest()


def normalize_job(job: JobData) -> JobData:
    normalized = job.model_copy(deep=True)
    normalized.title = plain_text(job.title)
    normalized.company = plain_text(job.company)
    normalized.description = plain_text(job.description)
    normalized.location = " ".join(job.location.split())
    normalized.url = canonical_url(job.url)
    normalized.source = job.source.strip().casefold()
    normalized.skills = sorted(
        {canonical_skill(skill) for skill in job.skills}
        | set(extract_skills(normalized.description + "\n" + normalized.title))
    )
    if not normalized.languages:
        normalized.languages = language_levels(normalized.description)
    if normalized.minimum_years is None:
        for sentence in re.split(r"[\n;]|(?<=[.!?])\s+", normalized.description):
            if re.search(r"\b(preferred|desirable|deseable|idealmente|nice to have)\b", folded(sentence)):
                continue
            match = re.search(r"\b(\d{1,2}(?:[.,]\d)?)\s*\+?\s*(?:years|años)\b", sentence, re.IGNORECASE)
            if match:
                normalized.minimum_years = float(match.group(1).replace(",", "."))
                break
    if normalized.seniority is None:
        match = re.search(r"\b(junior|mid|senior|lead|principal)\b", folded(normalized.title))
        if match:
            normalized.seniority = match.group(1)
    required = list(normalized.mandatory_requirements)
    for sentence in re.split(r"[\n;]|(?<=[.!?])\s+", normalized.description):
        if re.search(
            r"\b(must|required|mandatory|obligatorio|obligatoria|indispensable|excluyente|"
            r"debe contar|se requiere)\b",
            folded(sentence),
        ):
            if sentence.strip() and sentence.strip() not in required:
                required.append(sentence.strip()[:1500])
    normalized.mandatory_requirements = required[:100]
    return normalized
