"""Diagnostic repository persistence contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.analysis.domain.constants import DiagnosticSeverity
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic


class DiagnosticRepository(ABC):
    """Persistence contract for durable AnalysisDiagnostic records."""

    @abstractmethod
    def save_batch(self, diagnostics: list[AnalysisDiagnostic]) -> None:
        """Persist a batch of diagnostic records."""
        raise NotImplementedError

    @abstractmethod
    def list_by_analysis(
        self,
        analysis_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
        severity: DiagnosticSeverity | None = None,
        stage: str | None = None,
    ) -> list[AnalysisDiagnostic]:
        """List diagnostics for an analysis with filtering and pagination."""
        raise NotImplementedError

    @abstractmethod
    def count_by_analysis(
        self,
        analysis_id: UUID,
        severity: DiagnosticSeverity | None = None,
        stage: str | None = None,
    ) -> int:
        """Count diagnostics with optional severity and stage filters."""
        raise NotImplementedError
