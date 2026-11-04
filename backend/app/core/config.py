from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", case_sensitive=False)

    environment: str = "local"
    database_url: str = f"sqlite:///{ROOT / 'storage' / 'autojob.db'}"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "local-development-change-this-secret-before-sharing-12345"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    local_user_id: str = ""
    context_dir: Path = ROOT / "context"
    storage_dir: Path = ROOT / "storage"
    inline_tasks: bool = True
    max_cv_bytes: int = 10 * 1024 * 1024
    retention_days: int = Field(default=90, ge=1)
    timezone: str = "America/Bogota"
    llm_endpoint: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_provider: Literal["generic", "ollama"] = "generic"
    embedding_model: str = "nomic-embed-text"
    enable_embeddings: bool = False

    @field_validator("cors_origins")
    @classmethod
    def normalize_local_origins(cls, value: str) -> str:
        origins: list[str] = []
        for item in value.split(","):
            origin = item.strip().rstrip("/")
            if not origin:
                continue
            if origin not in origins:
                origins.append(origin)
            parsed = urlsplit(origin)
            if (
                parsed.scheme in {"http", "https"}
                and parsed.hostname in {"localhost", "127.0.0.1"}
                and not parsed.username
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            ):
                host = "127.0.0.1" if parsed.hostname == "localhost" else "localhost"
                port = f":{parsed.port}" if parsed.port is not None else ""
                alias = f"{parsed.scheme}://{host}{port}"
                if alias not in origins:
                    origins.append(alias)
        return ",".join(origins)

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        if self.environment != "local" and (
            len(self.secret_key) < 32
            or self.secret_key.startswith("local-development")
            or self.secret_key.startswith("replace-with")
        ):
            raise ValueError("SECRET_KEY debe ser aleatoria, privada y tener al menos 32 caracteres")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
