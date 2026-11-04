"""Job and Stage repository persistence contracts."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from backend.platform.analysis.domain.job import AnalysisJob, AnalysisStage


class JobRepository(ABC):
    """Persistence contract for background AnalysisJob entities."""

    @abstractmethod
    def save(self, job: AnalysisJob) -> AnalysisJob:
        """Persist a new job record."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, job_id: UUID) -> AnalysisJob | None:
        """Retrieve a job by its identifier."""
        raise NotImplementedError

    @abstractmethod
    def get_active_for_analysis(self, analysis_id: UUID) -> AnalysisJob | None:
        """Retrieve the currently active job for an analysis, if any."""
        raise NotImplementedError

    @abstractmethod
    def update(self, job: AnalysisJob, expected_version: int) -> AnalysisJob:
        """Update job with optimistic concurrency check."""
        raise NotImplementedError

    @abstractmethod
    def find_pending_jobs(self, created_cutoff: datetime) -> list[AnalysisJob]:
        """Find pending jobs old enough to require dispatch recovery."""
        raise NotImplementedError

    @abstractmethod
    def find_stale_jobs(self, heartbeat_cutoff: datetime) -> list[AnalysisJob]:
        """Find running jobs whose worker heartbeat is stale."""
        raise NotImplementedError


class StageRepository(ABC):
    """Persistence contract for AnalysisStage entities."""

    @abstractmethod
    def save(self, stage: AnalysisStage) -> AnalysisStage:
        """Persist a single stage record."""
        raise NotImplementedError

    @abstractmethod
    def save_batch(self, stages: list[AnalysisStage]) -> list[AnalysisStage]:
        """Persist initial batch of stage records for an analysis."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, stage_id: UUID) -> AnalysisStage | None:
        """Retrieve a stage by its identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_by_analysis(self, analysis_id: UUID) -> list[AnalysisStage]:
        """List all stages belonging to an analysis in sequential order."""
        raise NotImplementedError

    @abstractmethod
    def update(self, stage: AnalysisStage, expected_version: int) -> AnalysisStage:
        """Update stage with optimistic concurrency check."""
        raise NotImplementedError
