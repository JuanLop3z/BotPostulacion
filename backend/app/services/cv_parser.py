"""Conservative local extraction: unknown fields remain unknown, with evidence."""

import io
import re
import zipfile
from pathlib import Path

from app.schemas import CandidateProfile, Fact
from app.schemas.candidate import Experience
from app.services.text_utils import extract_skills, folded, language_levels

MAX_CV_BYTES = 10 * 1024 * 1024
MAX_CV_TEXT = 200000


class CVParseError(ValueError):
    pass


def extract_text(filename: str, content: bytes) -> str:
    if not content or len(content) > MAX_CV_BYTES:
        raise CVParseError("El CV debe contener datos y pesar como máximo 10 MB.")
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".txt":
            encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            text = content.decode(encoding)
            if "\x00" in text:
                raise CVParseError("El archivo TXT contiene datos binarios.")
        elif suffix == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise CVParseError("El contenido no corresponde a un PDF.")
            import pymupdf

            with pymupdf.open(stream=content, filetype="pdf") as document:
                if document.needs_pass:
                    raise CVParseError("El PDF está protegido por contraseña.")
                if document.page_count > 50:
                    raise CVParseError("El CV no puede superar 50 páginas.")
                text = "\n".join(page.get_text() for page in document)
        elif suffix == ".docx":
            if not zipfile.is_zipfile(io.BytesIO(content)):
                raise CVParseError("El contenido no corresponde a un DOCX.")
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(info.file_size for info in archive.infolist()) > 30 * 1024 * 1024:
                    raise CVParseError("El DOCX expandido supera el tamaño permitido.")
                if len(archive.infolist()) > 1000 or "word/document.xml" not in archive.namelist():
                    raise CVParseError("El DOCX no tiene una estructura válida.")
            from docx import Document

            document = Document(io.BytesIO(content))
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            paragraphs += [
                " | ".join(cell.text for cell in row.cells) for table in document.tables for row in table.rows
            ]
            text = "\n".join(paragraphs)
        else:
            raise CVParseError("Formato no permitido. Utiliza PDF, DOCX o TXT.")
    except CVParseError:
        raise
    except Exception as exc:
        raise CVParseError("No se pudo leer el documento; revisa su formato y contenido.") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) < 20:
        raise CVParseError("No se encontró texto suficiente; los CV escaneados necesitan OCR externo.")
    if len(text) > MAX_CV_TEXT:
        raise CVParseError("El documento contiene demasiado texto para ser un CV.")
    return text


def _label(text: str, *labels: str) -> str:
    for line in text.splitlines():
        for label in labels:
            match = re.match(rf"\s*{label}\s*:\s*(.+)", line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return ""


def _section_items(text: str, names: tuple[str, ...]) -> list[str]:
    lines = text.splitlines()
    result: list[str] = []
    in_section = False
    section_headings = {
        "educacion",
        "education",
        "certificaciones",
        "certifications",
        "proyectos",
        "projects",
        "experiencia",
        "experience",
        "habilidades",
        "skills",
        "idiomas",
        "languages",
        "resumen",
        "summary",
        "perfil",
        "profile",
        "contacto",
        "contact",
    }
    for line in lines:
        normalized = folded(line.strip().strip("#: "))
        if normalized in names:
            in_section = True
            continue
        if normalized in section_headings:
            in_section = False
        if in_section and line.strip():
            result.append(line.strip().lstrip("-• "))
        if len(result) >= 30:
            break
    return result


def parse_text(text: str) -> CandidateProfile:
    profile = CandidateProfile()
    profile.full_name = _label(text, "nombre", "name", "full name", "nombre completo")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not profile.full_name and lines:
        first = lines[0]
        if (
            2 <= len(first.split()) <= 5
            and not re.search(r"[\d@:/|]", first)
            and not any(
                word in folded(first)
                for word in (
                    "curriculum",
                    "resume",
                    "hoja de vida",
                    "developer",
                    "engineer",
                    "ingenier",
                    "senior",
                    "backend",
                    "frontend",
                    "software",
                    "analista",
                    "desarrollador",
                )
            )
        ):
            profile.full_name = first
    email = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE)
    profile.email = email.group() if email else ""
    profile.phone = _label(text, "teléfono", "telefono", "phone", "móvil", "movil", "celular")
    if not profile.phone:
        phone = re.search(r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?){2}\d{4}(?!\d)", text)
        profile.phone = phone.group().strip() if phone else ""
    profile.location = _label(text, "ubicación", "ubicacion", "location", "ciudad", "city")
    profile.title = _label(text, "título", "titulo", "cargo", "title", "profesión", "profesion", "role")
    profile.summary = _label(text, "resumen", "summary", "perfil profesional", "professional summary")
    profile.skills = extract_skills(text, skip_learning=True)
    profile.languages = language_levels(text)
    years = re.search(
        r"\b(\d{1,2}(?:[.,]\d)?)\s*(?:años|years)\s*(?:de\s*)?(?:experiencia|experience)\b",
        text,
        re.IGNORECASE,
    )
    if years:
        profile.experience_years = float(years.group(1).replace(",", "."))
    profile.education = _section_items(text, ("educacion", "education"))
    profile.certifications = _section_items(text, ("certificaciones", "certifications"))
    profile.projects = _section_items(text, ("proyectos", "projects"))
    for line in lines:
        # Explicit layout only: Company | Role | YYYY-MM - YYYY-MM/present.
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 3:
            dates = re.search(
                r"(\d{4}(?:-\d{2})?)\s*(?:–|—|\s-\s|hasta|to)\s*"
                r"(\d{4}(?:-\d{2})?|actualidad|presente|present|actual)",
                parts[2],
                re.I,
            )
            if dates:
                profile.experiences.append(
                    Experience(
                        company=parts[0],
                        role=parts[1],
                        start_date=dates.group(1),
                        end_date=dates.group(2),
                        technologies=extract_skills(line),
                        evidence=line,
                    )
                )
                profile.facts.append(
                    Fact(field="experiences", value=line, source="cv", evidence=line, verified=True)
                )
    for field in ("full_name", "email", "phone", "location", "title", "summary", "experience_years"):
        value = getattr(profile, field)
        if value is not None and value != "":
            evidence = next((line for line in lines if folded(str(value)) in folded(line)), str(value))
            if field == "experience_years" and years:
                evidence = years.group(0)
            profile.facts.append(
                Fact(field=field, value=str(value), source="cv", evidence=evidence, verified=True)
            )
    for field in ("skills", "education", "certifications", "projects"):
        for value in getattr(profile, field):
            evidence = next((line for line in lines if folded(value) in folded(line)), value)
            profile.facts.append(
                Fact(field=field, value=value, source="cv", evidence=evidence, verified=True)
            )
    for language, level in profile.languages.items():
        profile.facts.append(
            Fact(
                field=f"languages.{language}",
                value=level,
                source="cv",
                evidence=next((line for line in lines if level.casefold() in line.casefold()), level),
                verified=True,
            )
        )
    title_seniority = re.search(r"\b(junior|mid|senior|lead|principal)\b", folded(profile.title))
    if title_seniority:
        profile.seniority = title_seniority.group(1)
        profile.facts.append(
            Fact(
                field="seniority", value=profile.seniority, source="cv", evidence=profile.title, verified=True
            )
        )
    profile.extraction_notes = [
        "Extracción local conservadora. Revisa y completa los campos antes de preparar envíos.",
        "Las competencias mencionadas como aprendizaje no se consideran experiencia confirmada.",
    ]
    return profile


def parse_cv(filename: str, content: bytes) -> CandidateProfile:
    return parse_text(extract_text(filename, content))
