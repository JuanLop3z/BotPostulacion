from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    value: str
    source: Literal["cv", "context", "inference", "user"]
    evidence: str = ""
    verified: bool = False


class Experience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str
    role: str
    start_date: str = ""
    end_date: str = ""
    technologies: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    evidence: str = ""


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=80)
    location: str = Field(default="", max_length=300)
    title: str = Field(default="", max_length=300)
    skills: list[str] = Field(default_factory=list, max_length=300)
    experience_years: float | None = Field(default=None, ge=0, le=80)
    experiences: list[Experience] = Field(default_factory=list)
    seniority: str | None = None
    languages: dict[str, str] = Field(default_factory=dict)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=10000)
    facts: list[Fact] = Field(default_factory=list, max_length=1000)
    reviewed: bool = False
    extraction_notes: list[str] = Field(default_factory=list)
