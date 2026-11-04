"""Explicitly scoped connectors; no connector submits to a real employer by default."""

from app.integrations.base import (
    JobSourceAdapter,
    SourceCapabilities,
    SourceCapabilityError,
    SourceError,
    SubmissionResult,
)
from app.integrations.registry import get_source, list_sources

__all__ = [
    "JobSourceAdapter",
    "SourceCapabilities",
    "SourceCapabilityError",
    "SourceError",
    "SubmissionResult",
    "get_source",
    "list_sources",
]
