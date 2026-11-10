"""Analysis domain entity, configuration, completeness, and transition rules."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.platform.analysis.domain.constants import (
    ANALYSIS_TRANSITION_MATRIX,
    DEFAULT_MAX_ANALYSIS_DURATION_SECONDS,
    TERMINAL_ANALYSIS_STATES,
    AnalysisStatus,
)
from backend.platform.errors import AnalysisStateConflictError


@dataclass(frozen=True, slots=True)
class AnalysisConfiguration:
    """Immutable effective configuration applied to an analysis run."""

    include_paths: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = ()
    max_file_size_bytes: int = 5 * 1024 * 1024
    timeout_seconds: int = DEFAULT_MAX_ANALYSIS_DURATION_SECONDS
    custom_rules: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisCompleteness:
    """Immutable record of analysis coverage and completeness details."""

    analyzed_files_count: int = 0
    unsupported_files_count: int = 0
    failed_files_count: int = 0
    excluded_files_count: int = 0
    is_partial: bool = False
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisProgress:
    """Immutable snapshot of observable analysis progress."""

    current_stage: str | None = None
    completed_stages: tuple[str, ...] = ()
    total_stages: int = 0
    processed_items: int | None = None
    total_items: int | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class Analysis:
    """Authoritative Analysis lifecycle domain entity."""

    id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID  # Maps to Phase 2 RepositoryRevision.id
    status: AnalysisStatus
    configuration: AnalysisConfiguration
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    completeness: AnalysisCompleteness | None = None
    published_version_id: UUID | None = None
    error_message: str | None = None
    error_code: str | None = None
    version: int = 1

    @property
    def is_terminal(self) -> bool:
        """Return True if analysis is in an immutable terminal state."""
        return self.status in TERMINAL_ANALYSIS_STATES

    def can_transition_to(self, target: AnalysisStatus) -> bool:
        """Check whether transition to target status is valid under Section 9 matrix."""
        allowed = ANALYSIS_TRANSITION_MATRIX.get(self.status, frozenset())
        return target in allowed

    def transition_to(
        self,
        target: AnalysisStatus,
        *,
        updated_at: datetime,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        completeness: AnalysisCompleteness | None = None,
        published_version_id: UUID | None = None,
        error_message: str | None = None,
        error_code: str | None = None,
    ) -> Analysis:
        """Transition analysis to a new status, returning an updated immutable copy.

        Raises:
            AnalysisStateConflictError: If transition is not permitted.
        """
        if not self.can_transition_to(target):
            raise AnalysisStateConflictError(
                message=(
                    f"Cannot transition analysis from {self.status.value} to "
                    f"{target.value}."
                ),
                details={
                    "current_status": self.status.value,
                    "target_status": target.value,
                    "analysis_id": str(self.id),
                },
            )

        new_started_at = started_at if started_at is not None else self.started_at
        if target == AnalysisStatus.RUNNING and new_started_at is None:
            new_started_at = updated_at

        new_completed_at = (
            completed_at if completed_at is not None else self.completed_at
        )
        if target in TERMINAL_ANALYSIS_STATES and new_completed_at is None:
            new_completed_at = updated_at

        return Analysis(
            id=self.id,
            project_id=self.project_id,
            repository_id=self.repository_id,
            snapshot_id=self.snapshot_id,
            status=target,
            configuration=self.configuration,
            created_at=self.created_at,
            updated_at=updated_at,
            started_at=new_started_at,
            completed_at=new_completed_at,
            completeness=(
                completeness if completeness is not None else self.completeness
            ),
            published_version_id=(
                published_version_id
                if published_version_id is not None
                else self.published_version_id
            ),
            error_message=(
                error_message if error_message is not None else self.error_message
            ),
            error_code=error_code if error_code is not None else self.error_code,
            version=self.version + 1,
        )
