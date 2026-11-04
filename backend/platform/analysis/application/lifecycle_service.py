"""Application service orchestrating Analysis lifecycle operations."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.platform.analysis.application.dto import (
    AnalysisCompletenessResponse,
    AnalysisJobResponse,
    AnalysisListResponse,
    AnalysisResponse,
    AnalysisStageResponse,
    CreateAnalysisRequest,
)
from backend.platform.analysis.domain.analysis import (
    Analysis,
    AnalysisConfiguration,
)
from backend.platform.analysis.domain.constants import (
    DEFAULT_MAX_ANALYSIS_DURATION_SECONDS,
    AnalysisStageName,
    AnalysisStatus,
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
    JobStatus,
    StageStatus,
)
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.domain.event import (
    AnalysisEvent,
    AnalysisEventType,
)
from backend.platform.analysis.domain.job import AnalysisJob, AnalysisStage
from backend.platform.analysis.repositories.analysis_repo import AnalysisRepository
from backend.platform.analysis.repositories.diagnostic_repo import (
    DiagnosticRepository,
)
from backend.platform.analysis.repositories.event_repo import EventRepository
from backend.platform.analysis.repositories.job_repo import (
    JobRepository,
    StageRepository,
)
from backend.platform.errors import (
    AnalysisCancellationNotAllowedError,
    AnalysisInputError,
    AnalysisIntegrityError,
    AnalysisNotFoundError,
    AnalysisStateConflictError,
    RepositoryNotFoundError,
)
from backend.platform.ingestion.repositories.revision_repo import RevisionRepository
from backend.platform.projects.repositories.project_repo import ProjectRepository
from backend.platform.repositories.repositories.repository_repo import (
    RepositoryRepository,
)


class AnalysisLifecycleService:
    """Service providing transactional lifecycle operations for StackSense analyses."""

    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        job_repo: JobRepository,
        stage_repo: StageRepository,
        event_repo: EventRepository,
        diagnostic_repo: DiagnosticRepository,
        revision_repo: RevisionRepository,
        project_repo: ProjectRepository,
        repository_repo: RepositoryRepository,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._job_repo = job_repo
        self._stage_repo = stage_repo
        self._event_repo = event_repo
        self._diagnostic_repo = diagnostic_repo
        self._revision_repo = revision_repo
        self._project_repo = project_repo
        self._repository_repo = repository_repo

    def _to_analysis_response(
        self,
        analysis: Analysis,
        stages: list[AnalysisStage] | None = None,
        job: AnalysisJob | None = None,
    ) -> AnalysisResponse:
        stages_response = [
            AnalysisStageResponse(
                id=s.id,
                analysis_id=s.analysis_id,
                stage_name=s.stage_name,
                status=s.status.value,
                order=s.order,
                is_mandatory=s.is_mandatory,
                processed_items=s.processed_items,
                total_items=s.total_items,
                version=s.version,
                created_at=s.created_at,
                updated_at=s.updated_at,
                started_at=s.started_at,
                completed_at=s.completed_at,
                error_code=s.error_code,
                error_message=s.error_message,
            )
            for s in (stages or [])
        ]

        job_response = None
        if job is not None:
            job_response = AnalysisJobResponse(
                id=job.id,
                analysis_id=job.analysis_id,
                status=job.status.value,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                version=job.version,
                created_at=job.created_at,
                updated_at=job.updated_at,
                worker_id=job.worker_id,
                heartbeat_at=job.heartbeat_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_code=job.error_code,
                error_message=job.error_message,
            )

        completeness_response = None
        if analysis.completeness is not None:
            completeness_response = AnalysisCompletenessResponse(
                analyzed_files_count=analysis.completeness.analyzed_files_count,
                unsupported_files_count=analysis.completeness.unsupported_files_count,
                failed_files_count=analysis.completeness.failed_files_count,
                excluded_files_count=analysis.completeness.excluded_files_count,
                is_partial=analysis.completeness.is_partial,
                details=dict(analysis.completeness.details),
            )

        config_dict = {
            "include_paths": list(analysis.configuration.include_paths),
            "exclude_paths": list(analysis.configuration.exclude_paths),
            "max_file_size_bytes": analysis.configuration.max_file_size_bytes,
            "timeout_seconds": analysis.configuration.timeout_seconds,
            "custom_rules": [list(r) for r in analysis.configuration.custom_rules],
        }

        return AnalysisResponse(
            id=analysis.id,
            project_id=analysis.project_id,
            repository_id=analysis.repository_id,
            snapshot_id=analysis.snapshot_id,
            status=analysis.status.value,
            configuration=config_dict,
            version=analysis.version,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
            started_at=analysis.started_at,
            completed_at=analysis.completed_at,
            completeness=completeness_response,
            published_version_id=analysis.published_version_id,
            error_code=analysis.error_code,
            error_message=analysis.error_message,
            stages=stages_response,
            active_job=job_response,
        )

    def create_analysis(self, request: CreateAnalysisRequest) -> AnalysisResponse:
        """Transactionally create Analysis, initial Job, Stages, and created event."""
        # 1. Idempotency replay check
        if request.idempotency_key:
            existing = self._analysis_repo.get_by_idempotency_key(
                request.project_id,
                request.idempotency_key,
            )
            if existing is not None:
                stages = self._stage_repo.list_by_analysis(existing.id)
                job = self._job_repo.get_active_for_analysis(existing.id)
                return self._to_analysis_response(existing, stages, job)

        # 2. Validate prerequisites
        project = self._project_repo.get_by_id(request.project_id)
        if project is None:
            raise AnalysisInputError(
                message=f"Project '{request.project_id}' does not exist.",
                details={"project_id": str(request.project_id)},
            )

        repository = self._repository_repo.get_by_id(request.repository_id)
        if repository is None or repository.project_id != request.project_id:
            raise RepositoryNotFoundError()

        revision = self._revision_repo.get_by_id(request.revision_id)
        if revision is None:
            raise AnalysisInputError(
                message=f"Repository revision '{request.revision_id}' not found.",
                details={"revision_id": str(request.revision_id)},
            )
        if (
            revision.project_id != request.project_id
            or revision.repository_id != request.repository_id
        ):
            raise AnalysisIntegrityError(
                message=(
                    "Revision ownership chain does not match project or repository."
                ),
                details={
                    "revision_id": str(request.revision_id),
                    "project_id": str(request.project_id),
                    "repository_id": str(request.repository_id),
                },
            )

        # 3. Construct domain entities
        now = datetime.now(UTC)
        analysis_id = uuid4()
        job_id = uuid4()

        config = AnalysisConfiguration(
            include_paths=request.include_paths,
            exclude_paths=request.exclude_paths,
            max_file_size_bytes=request.max_file_size_bytes,
            timeout_seconds=request.timeout_seconds,
        )

        analysis = Analysis(
            id=analysis_id,
            project_id=request.project_id,
            repository_id=request.repository_id,
            snapshot_id=request.revision_id,
            status=AnalysisStatus.CREATED,
            configuration=config,
            created_at=now,
            updated_at=now,
        )

        job = AnalysisJob(
            id=job_id,
            analysis_id=analysis_id,
            project_id=request.project_id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        # Standard initial sequential stages
        standard_stage_names = [
            AnalysisStageName.INPUT_VALIDATION,
            AnalysisStageName.INVENTORY,
            AnalysisStageName.LANGUAGE_DETECTION,
            AnalysisStageName.FRAMEWORK_DETECTION,
            AnalysisStageName.SYNTAX_EXTRACTION,
            AnalysisStageName.IR_CONSTRUCTION,
            AnalysisStageName.IDENTITY_RESOLUTION,
            AnalysisStageName.ARCHITECTURE_BUILD,
            AnalysisStageName.PROJECTION,
        ]

        stages = [
            AnalysisStage(
                id=uuid4(),
                analysis_id=analysis_id,
                stage_name=name.value,
                status=StageStatus.PENDING,
                order=idx,
                is_mandatory=True,
                created_at=now,
                updated_at=now,
            )
            for idx, name in enumerate(standard_stage_names, start=1)
        ]

        created_event = AnalysisEvent(
            id=uuid4(),
            analysis_id=analysis_id,
            sequence_number=1,
            event_type=AnalysisEventType.ANALYSIS_CREATED,
            timestamp=now,
            payload={
                "project_id": str(request.project_id),
                "repository_id": str(request.repository_id),
                "snapshot_id": str(request.revision_id),
                "total_stages": len(stages),
            },
        )

        # 4. Save entities
        self._analysis_repo.save(
            analysis,
            idempotency_key=request.idempotency_key,
        )
        self._job_repo.save(job)
        self._stage_repo.save_batch(stages)
        self._event_repo.append(created_event)

        return self._to_analysis_response(analysis, stages, job)

    def get_analysis(
        self,
        analysis_id: UUID,
        project_id: UUID,
    ) -> AnalysisResponse:
        """Retrieve authoritative analysis representation."""
        analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
        if analysis is None:
            raise AnalysisNotFoundError()

        stages = self._stage_repo.list_by_analysis(analysis_id)
        job = self._job_repo.get_active_for_analysis(analysis_id)
        return self._to_analysis_response(analysis, stages, job)

    def list_analyses(
        self,
        project_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        status: AnalysisStatus | None = None,
    ) -> AnalysisListResponse:
        """List analyses for a project with deterministic pagination."""
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)

        items = self._analysis_repo.list_by_project(
            project_id,
            limit=safe_limit,
            offset=safe_offset,
            status=status,
        )
        total = self._analysis_repo.count_by_project(project_id, status)

        responses = [self._to_analysis_response(a) for a in items]
        return AnalysisListResponse(
            items=responses,
            total=total,
            limit=safe_limit,
            offset=safe_offset,
        )

    def cancel_analysis(
        self,
        analysis_id: UUID,
        project_id: UUID,
        reason: str | None = None,
    ) -> AnalysisResponse:
        """Request cancellation for an analysis."""
        analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
        if analysis is None:
            raise AnalysisNotFoundError()

        if analysis.is_terminal:
            raise AnalysisCancellationNotAllowedError(
                message=(
                    f"Analysis is in terminal state '{analysis.status.value}' "
                    "and cannot be cancelled."
                ),
                details={
                    "analysis_id": str(analysis_id),
                    "status": analysis.status.value,
                },
            )

        now = datetime.now(UTC)
        next_seq = self._event_repo.get_latest_sequence_number(analysis_id) + 1

        cancelled_job: AnalysisJob | None = None
        if analysis.status == AnalysisStatus.CREATED:
            # Cancellation before queue dispatch (CREATED -> FAILED per Section 9)
            updated = analysis.transition_to(
                AnalysisStatus.FAILED,
                updated_at=now,
                error_code="analysis_cancelled",
                error_message=reason or "Analysis cancelled before queue dispatch.",
            )
            self._analysis_repo.update(updated, expected_version=analysis.version)

            active_job = self._job_repo.get_active_for_analysis(analysis_id)
            if active_job and not active_job.is_terminal:
                cancelled_job = active_job.transition_to(
                    JobStatus.CANCELLED,
                    updated_at=now,
                    error_message=reason or "Job cancelled before queue dispatch.",
                )
                self._job_repo.update(
                    cancelled_job, expected_version=active_job.version
                )

            event = AnalysisEvent(
                id=uuid4(),
                analysis_id=analysis_id,
                sequence_number=next_seq,
                event_type=AnalysisEventType.ANALYSIS_CANCELLED,
                timestamp=now,
                payload={"reason": reason or "Cancelled before queue dispatch."},
            )
            self._event_repo.append(event)

        elif analysis.status == AnalysisStatus.QUEUED:
            # Direct queued cancellation (QUEUED -> CANCELLED per Section 9)
            updated = analysis.transition_to(
                AnalysisStatus.CANCELLED,
                updated_at=now,
                error_message=reason or "Analysis cancelled while queued.",
            )
            self._analysis_repo.update(updated, expected_version=analysis.version)

            active_job = self._job_repo.get_active_for_analysis(analysis_id)
            if active_job and not active_job.is_terminal:
                cancelled_job = active_job.transition_to(
                    JobStatus.CANCELLED,
                    updated_at=now,
                    error_message=reason or "Job cancelled while queued.",
                )
                self._job_repo.update(
                    cancelled_job, expected_version=active_job.version
                )

            event = AnalysisEvent(
                id=uuid4(),
                analysis_id=analysis_id,
                sequence_number=next_seq,
                event_type=AnalysisEventType.ANALYSIS_CANCELLED,
                timestamp=now,
                payload={"reason": reason or "Cancelled while queued."},
            )
            self._event_repo.append(event)

        elif analysis.status == AnalysisStatus.RUNNING:
            # Cooperative cancellation request
            updated = analysis.transition_to(
                AnalysisStatus.CANCEL_REQUESTED,
                updated_at=now,
            )
            self._analysis_repo.update(updated, expected_version=analysis.version)

            event = AnalysisEvent(
                id=uuid4(),
                analysis_id=analysis_id,
                sequence_number=next_seq,
                event_type=AnalysisEventType.ANALYSIS_CANCEL_REQUESTED,
                timestamp=now,
                payload={"reason": reason or "Cooperative cancellation requested."},
            )
            self._event_repo.append(event)
        else:
            raise AnalysisCancellationNotAllowedError(
                message=f"Cannot cancel analysis in status '{analysis.status.value}'.",
                details={"status": analysis.status.value},
            )

        stages = self._stage_repo.list_by_analysis(analysis_id)
        job = cancelled_job or self._job_repo.get_active_for_analysis(analysis_id)
        return self._to_analysis_response(updated, stages, job)

    def record_timeout(
        self,
        analysis_id: UUID,
        project_id: UUID,
        details: dict[str, Any] | None = None,
    ) -> AnalysisResponse:
        """Handle execution timeout (RUNNING -> TIMEOUT -> FAILED)."""
        analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
        if analysis is None:
            raise AnalysisNotFoundError()

        if analysis.status != AnalysisStatus.RUNNING:
            raise AnalysisStateConflictError(
                message=(
                    f"Cannot record timeout for analysis in status "
                    f"'{analysis.status.value}'."
                ),
                details={"status": analysis.status.value},
            )

        now = datetime.now(UTC)
        timeout_analysis = analysis.transition_to(
            AnalysisStatus.TIMEOUT,
            updated_at=now,
        )
        failed_analysis = timeout_analysis.transition_to(
            AnalysisStatus.FAILED,
            updated_at=now,
            error_code="analysis_timeout",
            error_message="Analysis exceeded maximum permitted duration limit.",
        )
        self._analysis_repo.update(failed_analysis, expected_version=analysis.version)

        # Mark active job as failed
        failed_job: AnalysisJob | None = None
        active_job = self._job_repo.get_active_for_analysis(analysis_id)
        if active_job and not active_job.is_terminal:
            failed_job = active_job.transition_to(
                JobStatus.FAILED,
                updated_at=now,
                error_code="analysis_timeout",
                error_message="Analysis job timed out.",
            )
            self._job_repo.update(failed_job, expected_version=active_job.version)

        # Record timeout diagnostic
        timeout_diag = AnalysisDiagnostic(
            id=uuid4(),
            analysis_id=analysis_id,
            code="analysis_timeout_exceeded",
            category=DiagnosticCategory.TIMEOUT,
            severity=DiagnosticSeverity.ERROR,
            scope=DiagnosticScope.ANALYSIS,
            message=(
                "Analysis execution exceeded maximum allowed time limit (30 minutes)."
            ),
            retryability=FailureRetryability.NON_RETRYABLE,
            created_at=now,
            details=details or {},
        )
        self._diagnostic_repo.save_batch([timeout_diag])

        # Record events
        next_seq = self._event_repo.get_latest_sequence_number(analysis_id) + 1
        timeout_event = AnalysisEvent(
            id=uuid4(),
            analysis_id=analysis_id,
            sequence_number=next_seq,
            event_type=AnalysisEventType.ANALYSIS_TIMEOUT,
            timestamp=now,
            payload={"max_duration_seconds": DEFAULT_MAX_ANALYSIS_DURATION_SECONDS},
        )
        failed_event = AnalysisEvent(
            id=uuid4(),
            analysis_id=analysis_id,
            sequence_number=next_seq + 1,
            event_type=AnalysisEventType.ANALYSIS_FAILED,
            timestamp=now,
            payload={"error_code": "analysis_timeout"},
        )
        self._event_repo.append(timeout_event)
        self._event_repo.append(failed_event)

        stages = self._stage_repo.list_by_analysis(analysis_id)
        job = failed_job or self._job_repo.get_active_for_analysis(analysis_id)
        return self._to_analysis_response(failed_analysis, stages, job)
