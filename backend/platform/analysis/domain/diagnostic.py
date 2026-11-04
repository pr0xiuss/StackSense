"""One M1-owned cross-module diagnostic contract and bounded collector."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.platform.analysis.domain.constants import (
    DEFAULT_MAX_DIAGNOSTICS_PER_ANALYSIS,
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
)


@dataclass(frozen=True, slots=True)
class AnalysisDiagnostic:
    """Canonical immutable diagnostic entity shared across all analysis modules."""

    id: UUID
    analysis_id: UUID
    code: str
    category: DiagnosticCategory
    severity: DiagnosticSeverity
    scope: DiagnosticScope
    message: str
    retryability: FailureRetryability
    created_at: datetime
    stage: str | None = None
    job_id: UUID | None = None
    details: dict[str, Any] = field(default_factory=dict)
    artifact_id: UUID | None = None
    artifact_path: str | None = None
    source_line: int | None = None
    source_column: int | None = None


class BoundedDiagnosticCollector:
    """In-memory diagnostic collector with capacity bounding."""

    def __init__(
        self,
        analysis_id: UUID,
        max_diagnostics: int = DEFAULT_MAX_DIAGNOSTICS_PER_ANALYSIS,
    ) -> None:
        self._analysis_id = analysis_id
        self._max_diagnostics = max_diagnostics
        self._diagnostics: list[AnalysisDiagnostic] = []
        self._dropped_count: int = 0
        self._overflow_recorded: bool = False

    @property
    def diagnostics(self) -> list[AnalysisDiagnostic]:
        """Return the collected list of diagnostics."""
        return list(self._diagnostics)

    @property
    def dropped_count(self) -> int:
        """Return count of dropped diagnostics due to capacity bounding."""
        return self._dropped_count

    @property
    def is_capped(self) -> bool:
        """Return True if collector reached capacity."""
        return self._overflow_recorded

    def add(self, diagnostic: AnalysisDiagnostic) -> bool:
        """Add a diagnostic to the collector.

        Returns True if the diagnostic was accepted, False if dropped due to capacity.
        """
        if len(self._diagnostics) < self._max_diagnostics:
            self._diagnostics.append(diagnostic)
            return True

        self._dropped_count += 1
        if not self._overflow_recorded:
            self._overflow_recorded = True
            overflow_diagnostic = AnalysisDiagnostic(
                id=uuid4(),
                analysis_id=self._analysis_id,
                code="diagnostic_capacity_exceeded",
                category=DiagnosticCategory.RESOURCE,
                severity=DiagnosticSeverity.WARNING,
                scope=DiagnosticScope.ANALYSIS,
                message=(
                    f"Diagnostic limit of {self._max_diagnostics} reached; "
                    "further diagnostics are aggregated."
                ),
                retryability=FailureRetryability.NON_RETRYABLE,
                created_at=datetime.now(UTC),
                details={"max_diagnostics": self._max_diagnostics},
            )
            self._diagnostics.append(overflow_diagnostic)
        return False
