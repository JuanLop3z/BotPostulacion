"""Validated, provider-neutral contracts for the application domain."""

from app.schemas.candidate import CandidateProfile, Fact
from app.schemas.context import ApplicationRules, ContextBundle, JobPreferences
from app.schemas.job import JobData, MatchResult

__all__ = [
    "ApplicationRules",
    "CandidateProfile",
    "ContextBundle",
    "Fact",
    "JobData",
    "JobPreferences",
    "MatchResult",
]
