"""SQLAlchemy implementations of JobRepository and StageRepository."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from backend.platform.analysis.domain.constants import JobStatus, StageStatus
from backend.platform.analysis.domain.job import AnalysisJob, AnalysisStage
from backend.platform.analysis.infra.lifecycle_model import (
    AnalysisJobModel,
    AnalysisStageModel,
)
from backend.platform.analysis.repositories.job_repo import (
    JobRepository,
    StageRepository,
)
from backend.platform.errors import AnalysisStateConflictError


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SqlAlchemyJobRepository(JobRepository):
    """PostgreSQL-backed implementation of JobRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: AnalysisJobModel) -> AnalysisJob:
        created_at = _ensure_utc(model.created_at)
        assert created_at is not None
        updated_at = _ensure_utc(model.updated_at)
        assert updated_at is not None
        return AnalysisJob(
            id=model.id,
            analysis_id=model.analysis_id,
            project_id=model.project_id,
            status=JobStatus(model.status),
            created_at=created_at,
            updated_at=updated_at,
            attempt=model.attempt,
            max_attempts=model.max_attempts,
            worker_id=model.worker_id,
            heartbeat_at=_ensure_utc(model.heartbeat_at),
            started_at=_ensure_utc(model.started_at),
            completed_at=_ensure_utc(model.completed_at),
            error_message=model.error_message,
            error_code=model.error_code,
            version=model.version,
        )

    def save(self, job: AnalysisJob) -> AnalysisJob:
        """Persist a new job record."""
        model = AnalysisJobModel(
            id=job.id,
            analysis_id=job.analysis_id,
            project_id=job.project_id,
            status=job.status.value,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
            worker_id=job.worker_id,
            heartbeat_at=job.heartbeat_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_code=job.error_code,
            error_message=job.error_message,
            version=job.version,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        self._session.add(model)
        self._session.flush()
        return job

    def get_by_id(self, job_id: UUID) -> AnalysisJob | None:
        """Retrieve a job by identifier."""
        model = self._session.get(AnalysisJobModel, job_id)
        if model is None:
            return None
        return self._to_domain(model)

    def get_active_for_analysis(self, analysis_id: UUID) -> AnalysisJob | None:
        """Retrieve the currently active job for an analysis, if any."""
        stmt = (
            select(AnalysisJobModel)
            .where(
                AnalysisJobModel.analysis_id == analysis_id,
                AnalysisJobModel.status.in_(
                    [
                        JobStatus.PENDING.value,
                        JobStatus.QUEUED.value,
                        JobStatus.RUNNING.value,
                        JobStatus.RETRYING.value,
                    ]
                ),
            )
            .order_by(AnalysisJobModel.attempt.desc())
            .limit(1)
        )
        model = self._session.scalar(stmt)
        if model is None:
            return None
        return self._to_domain(model)

    def update(self, job: AnalysisJob, expected_version: int) -> AnalysisJob:
        """Update job with optimistic concurrency check."""
        stmt = (
            update(AnalysisJobModel)
            .where(
                AnalysisJobModel.id == job.id,
                AnalysisJobModel.version == expected_version,
            )
            .values(
                status=job.status.value,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                worker_id=job.worker_id,
                heartbeat_at=job.heartbeat_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_code=job.error_code,
                error_message=job.error_message,
                version=job.version,
                updated_at=job.updated_at,
            )
        )
        result = self._session.execute(stmt)
        if isinstance(result, CursorResult) and result.rowcount == 0:
            raise AnalysisStateConflictError(
                message=(
                    f"Concurrency conflict: expected version {expected_version} "
                    f"for job '{job.id}'."
                ),
                details={"job_id": str(job.id), "expected_version": expected_version},
            )
        self._session.flush()
        return job

    def find_stale_jobs(self, heartbeat_cutoff: datetime) -> list[AnalysisJob]:
        """Find running jobs whose heartbeat is older than heartbeat_cutoff."""
        stmt = select(AnalysisJobModel).where(
            AnalysisJobModel.status == JobStatus.RUNNING.value,
            AnalysisJobModel.heartbeat_at < heartbeat_cutoff,
        )
        models = self._session.scalars(stmt).all()
        return [self._to_domain(m) for m in models]

    def find_pending_jobs(self, created_cutoff: datetime) -> list[AnalysisJob]:
        """Find pending jobs old enough to require dispatch recovery."""
        stmt = select(AnalysisJobModel).where(
            AnalysisJobModel.status == JobStatus.PENDING.value,
            AnalysisJobModel.created_at < created_cutoff,
        )
        models = self._session.scalars(stmt).all()
        return [self._to_domain(m) for m in models]


class SqlAlchemyStageRepository(StageRepository):
    """PostgreSQL-backed implementation of StageRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: AnalysisStageModel) -> AnalysisStage:
        created_at = _ensure_utc(model.created_at)
        assert created_at is not None
        updated_at = _ensure_utc(model.updated_at)
        assert updated_at is not None
        return AnalysisStage(
            id=model.id,
            analysis_id=model.analysis_id,
            job_id=model.job_id,
            stage_name=model.stage_name,
            status=StageStatus(model.status),
            order=model.stage_order,
            is_mandatory=model.is_mandatory,
            processed_items=model.processed_items,
            total_items=model.total_items,
            started_at=_ensure_utc(model.started_at),
            completed_at=_ensure_utc(model.completed_at),
            error_code=model.error_code,
            error_message=model.error_message,
            version=model.version,
            created_at=created_at,
            updated_at=updated_at,
        )

    def save(self, stage: AnalysisStage) -> AnalysisStage:
        """Persist a single stage record."""
        model = AnalysisStageModel(
            id=stage.id,
            analysis_id=stage.analysis_id,
            job_id=stage.job_id,
            stage_name=stage.stage_name,
            status=stage.status.value,
            stage_order=stage.order,
            is_mandatory=stage.is_mandatory,
            processed_items=stage.processed_items,
            total_items=stage.total_items,
            started_at=stage.started_at,
            completed_at=stage.completed_at,
            error_code=stage.error_code,
            error_message=stage.error_message,
            version=stage.version,
            created_at=stage.created_at,
            updated_at=stage.updated_at,
        )
        self._session.add(model)
        self._session.flush()
        return stage

    def save_batch(self, stages: list[AnalysisStage]) -> list[AnalysisStage]:
        """Persist a batch of stage records."""
        for stage in stages:
            model = AnalysisStageModel(
                id=stage.id,
                analysis_id=stage.analysis_id,
                job_id=stage.job_id,
                stage_name=stage.stage_name,
                status=stage.status.value,
                stage_order=stage.order,
                is_mandatory=stage.is_mandatory,
                processed_items=stage.processed_items,
                total_items=stage.total_items,
                started_at=stage.started_at,
                completed_at=stage.completed_at,
                error_code=stage.error_code,
                error_message=stage.error_message,
                version=stage.version,
                created_at=stage.created_at,
                updated_at=stage.updated_at,
            )
            self._session.add(model)
        self._session.flush()
        return stages

    def get_by_id(self, stage_id: UUID) -> AnalysisStage | None:
        """Retrieve a stage by identifier."""
        model = self._session.get(AnalysisStageModel, stage_id)
        if model is None:
            return None
        return self._to_domain(model)

    def get_by_name(self, analysis_id: UUID, stage_name: str) -> AnalysisStage | None:
        """Retrieve a specific stage by name within an analysis."""
        stmt = select(AnalysisStageModel).where(
            AnalysisStageModel.analysis_id == analysis_id,
            AnalysisStageModel.stage_name == stage_name,
        )
        model = self._session.scalar(stmt)
        if model is None:
            return None
        return self._to_domain(model)

    def list_by_analysis(self, analysis_id: UUID) -> list[AnalysisStage]:
        """List all stages belonging to an analysis ordered by stage_order."""
        stmt = (
            select(AnalysisStageModel)
            .where(AnalysisStageModel.analysis_id == analysis_id)
            .order_by(AnalysisStageModel.stage_order)
        )
        models = self._session.scalars(stmt).all()
        return [self._to_domain(m) for m in models]

    def update(self, stage: AnalysisStage, expected_version: int) -> AnalysisStage:
        """Update stage with optimistic concurrency check."""
        stmt = (
            update(AnalysisStageModel)
            .where(
                AnalysisStageModel.id == stage.id,
                AnalysisStageModel.version == expected_version,
            )
            .values(
                status=stage.status.value,
                job_id=stage.job_id,
                processed_items=stage.processed_items,
                total_items=stage.total_items,
                started_at=stage.started_at,
                completed_at=stage.completed_at,
                error_code=stage.error_code,
                error_message=stage.error_message,
                version=stage.version,
                updated_at=stage.updated_at,
            )
        )
        result = self._session.execute(stmt)
        if isinstance(result, CursorResult) and result.rowcount == 0:
            raise AnalysisStateConflictError(
                message=(
                    f"Concurrency conflict: expected version {expected_version} "
                    f"for stage '{stage.stage_name}'."
                ),
                details={
                    "stage_id": str(stage.id),
                    "stage_name": stage.stage_name,
                    "expected_version": expected_version,
                },
            )
        self._session.flush()
        return stage
