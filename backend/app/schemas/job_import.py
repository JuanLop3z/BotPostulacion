from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssistedJobImport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: Literal["linkedin", "computrabajo", "manual"]
    url: str = Field(min_length=10, max_length=3000)
    title: str = Field(min_length=2, max_length=500)
    company: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=20, max_length=100000)
    location: str = Field(default="", max_length=500)
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    salary_min: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    salary_max: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    salary_period: Literal["month", "year", "hour", "unknown"] = "unknown"
    minimum_years: float | None = Field(default=None, ge=0, le=80)
    contract_type: str = Field(default="", max_length=100)
    mandatory_requirements: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("mandatory_requirements")
    @classmethod
    def bounded_requirements(cls, values: list[str]) -> list[str]:
        result = []
        for value in values:
            if len(value) > 1500:
                raise ValueError("Cada requisito debe tener como máximo 1500 caracteres")
            if value.strip():
                result.append(value.strip())
        return result

    @model_validator(mode="after")
    def consistent_import(self) -> "AssistedJobImport":
        parts = urlsplit(self.url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise ValueError("Pega el enlace HTTPS de la oferta, sin credenciales")
        if parts.port not in (None, 443):
            raise ValueError("El enlace debe usar el puerto HTTPS estándar")
        host = parts.hostname.lower()
        root = {"linkedin": "linkedin.com", "computrabajo": "computrabajo.com"}.get(self.source)
        if root and host != root and not host.endswith("." + root):
            raise ValueError("El dominio del enlace no corresponde al portal seleccionado")
        if self.source == "computrabajo" and "/ofertas-de-trabajo/" not in parts.path:
            raise ValueError("Pega el enlace de una oferta concreta de Computrabajo")
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("El salario mínimo de la oferta no puede superar el máximo")
        if self.salary_min is not None or self.salary_max is not None:
            if self.currency is None or self.salary_period == "unknown":
                raise ValueError("Indica moneda y periodicidad cuando la oferta publique salario")
        return self
