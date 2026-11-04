import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _default_modes() -> list[Literal["remote", "hybrid", "onsite", "unknown"]]:
    return ["remote", "hybrid"]


class JobPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    preferred_cities: list[str] = Field(default_factory=list)
    relocation_allowed: bool | None = None
    work_modes: list[Literal["remote", "hybrid", "onsite", "unknown"]] = Field(default_factory=_default_modes)
    currency: str = "USD"
    minimum_monthly: float | None = Field(default=None, ge=0)
    desired_monthly: float | None = Field(default=None, ge=0)
    desired_monthly_max: float | None = Field(default=None, ge=0)
    salary_below_minimum_requires_review: bool = False
    salary_basis: Literal["gross", "net", "unknown"] = "unknown"
    contract_types: list[str] = Field(default_factory=list)
    preferred_contract_types: list[str] = Field(default_factory=list)
    availability_note: str = Field(default="", max_length=1000)
    seniority: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    preferred_stack: list[str] = Field(default_factory=list)
    excluded_technologies: list[str] = Field(default_factory=list)
    required_languages: dict[str, str] = Field(default_factory=dict)
    industries: list[str] = Field(default_factory=list)
    excluded_companies: list[str] = Field(default_factory=list)
    excluded_titles: list[str] = Field(default_factory=list)
    positive_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)


class ApplicationRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_score: float = Field(default=70, ge=0, le=100)
    max_daily: int = Field(default=10, ge=0, le=1000)
    max_weekly: int = Field(default=40, ge=0, le=5000)
    permitted_sources: list[str] = Field(default_factory=lambda: ["remotive", "greenhouse", "demo"])
    mode: Literal["manual", "semi_automatic", "automatic"] = "semi_automatic"
    requires_approval: bool = True
    automatic_enabled: bool = False
    third_party_consent: bool = False
    llm_consent: bool = False
    max_retries: int = Field(default=2, ge=0, le=5)
    search_interval_hours: int = Field(default=6, ge=6, le=168)
    matching_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "technical": 0.30,
            "experience": 0.20,
            "seniority": 0.15,
            "preferences": 0.15,
            "salary": 0.10,
            "languages": 0.10,
        }
    )

    @field_validator("matching_weights")
    @classmethod
    def validate_weights(cls, value: dict[str, float]) -> dict[str, float]:
        expected = {"technical", "experience", "seniority", "preferences", "salary", "languages"}
        if set(value) != expected or any(
            not math.isfinite(weight) or weight < 0 or weight > 100 for weight in value.values()
        ):
            raise ValueError("Los pesos deben incluir los seis criterios y ser no negativos.")
        if sum(value.values()) <= 0:
            raise ValueError("La suma de los pesos debe ser mayor que cero.")
        return value


class ContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_context: str = Field(default="", max_length=50000)
    custom_instructions: str = Field(default="", max_length=20000)
    preferences: JobPreferences = Field(default_factory=JobPreferences)
    rules: ApplicationRules = Field(default_factory=ApplicationRules)
