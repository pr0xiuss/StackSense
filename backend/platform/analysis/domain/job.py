"""AnalysisJob and AnalysisStage domain entities and transition rules."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.platform.analysis.domain.constants import (
    JOB_TRANSITION_MATRIX,
    STAGE_TRANSITION_MATRIX,
    TERMINAL_JOB_STATES,
    TERMINAL_STAGE_STATES,
    JobStatus,
    StageStatus,
)
from backend.platform.errors import AnalysisStateConflictError


@dataclass(frozen=True, slots=True)
class AnalysisJob:
    """Background execution job domain entity."""

    id: UUID
    analysis_id: UUID
    project_id: UUID
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    attempt: int = 1
    max_attempts: int = 3
    worker_id: str | None = None
    heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    error_code: str | None = None
    version: int = 1

    @property
    def is_terminal(self) -> bool:
        """Return True if job is in a terminal state."""
        return self.status in TERMINAL_JOB_STATES

    def can_transition_to(self, target: JobStatus) -> bool:
        """Check whether transition to target status is valid."""
        allowed = JOB_TRANSITION_MATRIX.get(self.status, frozenset())
        return target in allowed

    def transition_to(
        self,
        target: JobStatus,
        *,
        updated_at: datetime,
        worker_id: str | None = None,
        heartbeat_at: datetime | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
        error_code: str | None = None,
        increment_attempt: bool = False,
    ) -> AnalysisJob:
        """Transition job to target status, returning an updated immutable copy."""
        if not self.can_transition_to(target):
            raise AnalysisStateConflictError(
                message=(
                    f"Cannot transition job from {self.status.value} to "
                    f"{target.value}."
                ),
                details={
                    "current_status": self.status.value,
                    "target_status": target.value,
                    "job_id": str(self.id),
                    "analysis_id": str(self.analysis_id),
                },
            )

        new_started_at = started_at if started_at is not None else self.started_at
        if target == JobStatus.RUNNING and new_started_at is None:
            new_started_at = updated_at

        new_completed_at = (
            completed_at if completed_at is not None else self.completed_at
        )
        if target in TERMINAL_JOB_STATES and new_completed_at is None:
            new_completed_at = updated_at

        new_attempt = self.attempt + 1 if increment_attempt else self.attempt

        return AnalysisJob(
            id=self.id,
            analysis_id=self.analysis_id,
            project_id=self.project_id,
            status=target,
            created_at=self.created_at,
            updated_at=updated_at,
            attempt=new_attempt,
            max_attempts=self.max_attempts,
            worker_id=worker_id if worker_id is not None else self.worker_id,
            heartbeat_at=(
                heartbeat_at if heartbeat_at is not None else self.heartbeat_at
            ),
            started_at=new_started_at,
            completed_at=new_completed_at,
            error_message=(
                error_message if error_message is not None else self.error_message
            ),
            error_code=error_code if error_code is not None else self.error_code,
            version=self.version + 1,
        )

    def update_heartbeat(self, heartbeat_at: datetime) -> AnalysisJob:
        """Update job heartbeat timestamp without changing status."""
        return AnalysisJob(
            id=self.id,
            analysis_id=self.analysis_id,
            project_id=self.project_id,
            status=self.status,
            created_at=self.created_at,
            updated_at=heartbeat_at,
            attempt=self.attempt,
            max_attempts=self.max_attempts,
            worker_id=self.worker_id,
            heartbeat_at=heartbeat_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error_message=self.error_message,
            error_code=self.error_code,
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class AnalysisStage:
    """Individual bounded analysis stage domain entity."""

    id: UUID
    analysis_id: UUID
    stage_name: str
    status: StageStatus
    order: int
    created_at: datetime
    updated_at: datetime
    job_id: UUID | None = None
    processed_items: int = 0
    total_items: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    error_code: str | None = None
    is_mandatory: bool = True
    version: int = 1

    @property
    def is_terminal(self) -> bool:
        """Return True if stage is in a terminal state."""
        return self.status in TERMINAL_STAGE_STATES

    def can_transition_to(self, target: StageStatus) -> bool:
        """Check whether transition to target stage status is valid."""
        allowed = STAGE_TRANSITION_MATRIX.get(self.status, frozenset())
        return target in allowed

    def transition_to(
        self,
        target: StageStatus,
        *,
        updated_at: datetime,
        job_id: UUID | None = None,
        processed_items: int | None = None,
        total_items: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
        error_code: str | None = None,
    ) -> AnalysisStage:
        """Transition stage to target status, returning an updated immutable copy."""
        if not self.can_transition_to(target):
            raise AnalysisStateConflictError(
                message=(
                    f"Cannot transition stage '{self.stage_name}' from "
                    f"{self.status.value} to {target.value}."
                ),
                details={
                    "current_status": self.status.value,
                    "target_status": target.value,
                    "stage_id": str(self.id),
                    "stage_name": self.stage_name,
                    "analysis_id": str(self.analysis_id),
                },
            )

        new_started_at = started_at if started_at is not None else self.started_at
        if target == StageStatus.RUNNING and new_started_at is None:
            new_started_at = updated_at

        new_completed_at = (
            completed_at if completed_at is not None else self.completed_at
        )
        if target in TERMINAL_STAGE_STATES and new_completed_at is None:
            new_completed_at = updated_at

        return AnalysisStage(
            id=self.id,
            analysis_id=self.analysis_id,
            stage_name=self.stage_name,
            status=target,
            order=self.order,
            created_at=self.created_at,
            updated_at=updated_at,
            job_id=job_id if job_id is not None else self.job_id,
            processed_items=(
                processed_items if processed_items is not None else self.processed_items
            ),
            total_items=total_items if total_items is not None else self.total_items,
            started_at=new_started_at,
            completed_at=new_completed_at,
            error_message=(
                error_message if error_message is not None else self.error_message
            ),
            error_code=error_code if error_code is not None else self.error_code,
            is_mandatory=self.is_mandatory,
            version=self.version + 1,
        )

    def update_progress(
        self,
        processed_items: int,
        total_items: int,
        *,
        updated_at: datetime,
    ) -> AnalysisStage:
        """Update stage item progress counts without changing status."""
        return AnalysisStage(
            id=self.id,
            analysis_id=self.analysis_id,
            stage_name=self.stage_name,
            status=self.status,
            order=self.order,
            created_at=self.created_at,
            updated_at=updated_at,
            job_id=self.job_id,
            processed_items=processed_items,
            total_items=total_items,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error_message=self.error_message,
            error_code=self.error_code,
            is_mandatory=self.is_mandatory,
            version=self.version + 1,
        )
