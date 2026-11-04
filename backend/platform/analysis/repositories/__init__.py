"""Abstract persistence interfaces for the analysis domain."""

from backend.platform.analysis.repositories.analysis_repo import AnalysisRepository
from backend.platform.analysis.repositories.diagnostic_repo import DiagnosticRepository
from backend.platform.analysis.repositories.event_repo import EventRepository
from backend.platform.analysis.repositories.job_repo import (
    JobRepository,
    StageRepository,
)

__all__ = [
    "AnalysisRepository",
    "DiagnosticRepository",
    "EventRepository",
    "JobRepository",
    "StageRepository",
]
