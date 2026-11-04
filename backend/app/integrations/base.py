"""Provider boundaries expose capabilities instead of assuming a public apply API."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.schemas import JobData


class SourceCapabilities(BaseModel):
    search: bool = True
    details: bool = False
    requirements: bool = False
    salary: bool = False
    application_method: bool = True
    prepare: bool = True
    submit: bool = False
    status: bool = False


class SourceError(Exception):
    """Sanitized provider error, with retry behavior kept explicit for the worker."""

    def __init__(
        self,
        message: str,
        *,
        transient: bool = False,
        retry_after: int | None = None,
        requires_human: bool = False,
    ) -> None:
        super().__init__(message)
        self.transient = transient
        self.retry_after = retry_after
        self.requires_human = requires_human


class SourceCapabilityError(SourceError):
    pass


class SubmissionResult(BaseModel):
    submitted: bool
    confirmed: bool = False
    reference: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class JobSourceAdapter(ABC):
    name: str
    label: str
    description: str
    capabilities = SourceCapabilities()
    minimum_refresh_hours: int = 6

    @abstractmethod
    def search(self, query: str = "", board: str | None = None) -> list[JobData]:
        """Fetch only from the connector's fixed documented API host."""

    def details(self, external_id: str, board: str | None = None) -> JobData:
        raise SourceCapabilityError(f"{self.label}: detalles individuales no disponibles.")

    def prepare(self, packet: dict[str, Any]) -> dict[str, Any]:
        """Preparation is local. Provider descriptions are never executable instructions."""
        return dict(packet)

    def submit(self, application_id: str, packet: dict[str, Any]) -> SubmissionResult:
        raise SourceCapabilityError(
            f"{self.label} no dispone de envío autorizado. Complete el proceso en su portal.",
            requires_human=True,
        )

    def status(self, reference: str) -> SubmissionResult:
        raise SourceCapabilityError(f"{self.label}: consulta de estado no disponible.")

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "capabilities": self.capabilities.model_dump(),
            "minimum_refresh_hours": self.minimum_refresh_hours,
        }
