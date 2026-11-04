"""A small registry is the only place needed to install a new connector."""

from typing import Any

from app.integrations.assisted import (
    ComputrabajoAssistedAdapter,
    LinkedInAssistedAdapter,
    ManualSourceAdapter,
)
from app.integrations.base import JobSourceAdapter, SourceCapabilityError
from app.integrations.demo import DemoAdapter
from app.integrations.greenhouse import GreenhouseAdapter
from app.integrations.remotive import RemotiveAdapter

_ADAPTERS: dict[str, type[JobSourceAdapter]] = {
    "remotive": RemotiveAdapter,
    "greenhouse": GreenhouseAdapter,
    "demo": DemoAdapter,
    "linkedin": LinkedInAssistedAdapter,
    "computrabajo": ComputrabajoAssistedAdapter,
    "manual": ManualSourceAdapter,
}


def get_source(name: str) -> JobSourceAdapter:
    adapter = _ADAPTERS.get(name)
    if adapter is None:
        raise SourceCapabilityError(
            "Fuente no disponible. Use una integración documentada o el enlace manual."
        )
    return adapter()


def list_sources() -> list[dict[str, Any]]:
    return [adapter().describe() for adapter in _ADAPTERS.values()]
