from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=80)
    external_id: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=500)
    company: str = Field(min_length=1, max_length=300)
    url: str = Field(max_length=3000)
    description: str = Field(default="", max_length=200000)
    location: str = Field(default="", max_length=500)
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    skills: list[str] = Field(default_factory=list)
    minimum_years: float | None = Field(default=None, ge=0, le=80)
    seniority: str | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str | None = None
    salary_period: Literal["month", "year", "hour", "unknown"] = "unknown"
    languages: dict[str, str] = Field(default_factory=dict)
    mandatory_requirements: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    contract_type: str = ""
    ingestion_method: Literal["api", "assisted"] = "api"

    @field_validator("url")
    @classmethod
    def safe_link(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username:
            raise ValueError("La oferta debe tener una URL HTTP(S) sin credenciales.")
        return value


class MatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=100)
    eligible: bool
    decision: str
    matches: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    breakdown: dict[str, float] = Field(default_factory=dict)
    method: str = "rules_keywords"
    requires_human_review: bool = False
