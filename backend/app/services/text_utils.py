import re
import unicodedata
from html import unescape
from html.parser import HTMLParser


def folded(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in value if not unicodedata.combining(character))


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag in {"br", "p", "li", "div", "h1", "h2", "h3"}:
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        if tag in {"p", "li", "div"}:
            self.chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.chunks.append(data)


def plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    text = unescape("".join(parser.chunks))
    return "\n".join(
        line for line in (re.sub(r"[\t \xa0]+", " ", line).strip() for line in text.splitlines()) if line
    )


SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "Java": ("java",),
    "JavaScript": ("javascript",),
    "TypeScript": ("typescript",),
    "C#": ("c#", "c sharp"),
    "C++": ("c++",),
    "Go": ("golang", "go"),
    "Rust": ("rust",),
    "PHP": ("php",),
    "Ruby": ("ruby",),
    "Kotlin": ("kotlin",),
    "Swift": ("swift",),
    "SQL": ("sql",),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
    "Flask": ("flask",),
    "Spring Boot": ("spring boot", "springboot"),
    "Spring": ("spring",),
    "React": ("react", "react.js", "reactjs"),
    "Next.js": ("next.js", "nextjs"),
    "Vue": ("vue", "vue.js", "vuejs"),
    "Angular": ("angular",),
    "Node.js": ("node.js", "nodejs"),
    "Express": ("express", "express.js"),
    ".NET": (".net", "dotnet"),
    "PostgreSQL": ("postgresql", "postgres"),
    "MySQL": ("mysql",),
    "SQL Server": ("sql server", "mssql"),
    "MongoDB": ("mongodb", "mongo db"),
    "Redis": ("redis",),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure",),
    "GCP": ("gcp", "google cloud"),
    "Git": ("git",),
    "GitHub Actions": ("github actions",),
    "Terraform": ("terraform",),
    "Linux": ("linux",),
    "REST APIs": ("rest api", "rest apis", "apis rest", "api rest", "restful"),
    "GraphQL": ("graphql",),
    "Microservices": ("microservices", "microservicios"),
    "Kafka": ("kafka",),
    "RabbitMQ": ("rabbitmq",),
    "Celery": ("celery",),
    "Pandas": ("pandas",),
    "NumPy": ("numpy",),
    "PyTorch": ("pytorch",),
    "TensorFlow": ("tensorflow",),
    "Playwright": ("playwright",),
    "Selenium": ("selenium",),
    "Agile": ("agile", "agil"),
    "Scrum": ("scrum",),
}


def contains_term(text: str, term: str) -> bool:
    return re.search(r"(?<![\w])" + re.escape(folded(term)) + r"(?![\w])", folded(text)) is not None


def canonical_skill(value: str) -> str:
    normalized = folded(value.strip())
    for canonical, aliases in SKILL_ALIASES.items():
        if normalized in {folded(canonical), *aliases}:
            return canonical
    return value.strip()


def extract_skills(text: str, *, skip_learning: bool = False) -> list[str]:
    parts = re.split(r"[\n;]|(?<=[.!?])\s+", text)
    if skip_learning:
        parts = [
            part
            for part in parts
            if not re.search(
                r"\b(aprendiendo|learning|estudiando|sin experiencia|no conozco|no domino|"
                r"no experience|not familiar|interesado en aprender|want to learn)\b",
                folded(part),
            )
        ]
    return [
        canonical
        for canonical, aliases in SKILL_ALIASES.items()
        if any(contains_term(part, alias) for alias in aliases for part in parts)
    ]


def language_levels(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for language, aliases in {
        "english": ("english", "ingles"),
        "spanish": ("spanish", "espanol", "castellano"),
        "portuguese": ("portuguese", "portugues"),
        "french": ("french", "frances"),
        "german": ("german", "aleman"),
    }.items():
        for alias in aliases:
            match = re.search(
                rf"\b{alias}\b[^\n.;]{{0,25}}?\b(a1|a2|b1|b2|c1|c2|native|nativo|"
                rf"nativa|basic|basico|intermediate|intermedio|advanced|avanzado|fluent)\b",
                folded(text),
            )
            if match:
                result[language] = match.group(1).upper()
                break
    return result
