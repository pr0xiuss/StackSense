"""Analysis execution orchestrator for background job and stage pipeline execution."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.platform.analysis.application.events import LifecycleEventEmitter
from backend.platform.analysis.application.execution import (
    AnalysisStageHandler,
    ExecutionContext,
)
from backend.platform.analysis.application.input_factory import AnalysisInputFactory
from backend.platform.analysis.application.registry import StageHandlerRegistry
from backend.platform.analysis.domain.constants import (
    DEFAULT_MAX_ANALYSIS_DURATION_SECONDS,
    AnalysisStatus,
    JobStatus,
    StageStatus,
)
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.domain.event import AnalysisEventType
from backend.platform.analysis.domain.input import AnalysisInput
from backend.platform.analysis.repositories.analysis_repo import AnalysisRepository
from backend.platform.analysis.repositories.diagnostic_repo import DiagnosticRepository
from backend.platform.analysis.repositories.event_repo import EventRepository
from backend.platform.analysis.repositories.job_repo import (
    JobRepository,
    StageRepository,
)
from backend.platform.errors import (
    AnalysisCancelledError,
    AnalysisConfigurationError,
    AnalysisNotFoundError,
    AnalysisTimeoutError,
)

logger = logging.getLogger(__name__)


class _DefaultExecutionContext(ExecutionContext):
    """Runtime ExecutionContext implementation provided to stage handlers."""

    def __init__(
        self,
        *,
        analysis_id: UUID,
        project_id: UUID,
        job_id: UUID,
        stage_id: UUID,
        stage_name: str,
        input_data: AnalysisInput,
        analysis_repo: AnalysisRepository,
        job_repo: JobRepository,
        stage_repo: StageRepository,
        diagnostic_repo: DiagnosticRepository,
        event_emitter: LifecycleEventEmitter,
    ) -> None:
        self._analysis_id = analysis_id
        self._project_id = project_id
        self._job_id = job_id
        self._stage_id = stage_id
        self._stage_name = stage_name
        self._input = input_data
        self._analysis_repo = analysis_repo
        self._job_repo = job_repo
        self._stage_repo = stage_repo
        self._diagnostic_repo = diagnostic_repo
        self._event_emitter = event_emitter

    @property
    def analysis_id(self) -> UUID:
        return self._analysis_id

    @property
    def project_id(self) -> UUID:
        return self._project_id

    @property
    def job_id(self) -> UUID:
        return self._job_id

    @property
    def stage_id(self) -> UUID:
        return self._stage_id

    @property
    def stage_name(self) -> str:
        return self._stage_name

    @property
    def input(self) -> AnalysisInput:
        return self._input

    def is_cancellation_requested(self) -> bool:
        """Inspect persisted analysis status to check for cancellation request."""
        analysis = self._analysis_repo.get_by_id(self._analysis_id, self._project_id)
        if analysis is None:
            return False
        return analysis.status in (
            AnalysisStatus.CANCEL_REQUESTED,
            AnalysisStatus.CANCELLED,
        )

    def report_progress(
        self,
        processed_items: int,
        total_items: int,
        message: str | None = None,
    ) -> None:
        """Update stage item progress and emit heartbeat and progress event."""
        now = datetime.now(UTC)

        # Update stage progress
        stage = self._stage_repo.get_by_id(self._stage_id)
        if stage and not stage.is_terminal:
            updated_stage = stage.update_progress(
                processed_items=processed_items,
                total_items=total_items,
                updated_at=now,
            )
            self._stage_repo.update(updated_stage, expected_version=stage.version)

        # Update job heartbeat
        job = self._job_repo.get_by_id(self._job_id)
        if job and not job.is_terminal:
            updated_job = job.update_heartbeat(heartbeat_at=now)
            self._job_repo.update(updated_job, expected_version=job.version)

        self._event_emitter.emit_stage_progress(
            self._stage_name,
            self._stage_id,
            processed_items,
            total_items,
            message,
        )

    def record_diagnostic(self, diagnostic: AnalysisDiagnostic) -> None:
        """Persist diagnostic finding."""
        self._diagnostic_repo.save_batch([diagnostic])

    def record_event(
        self,
        event_type: AnalysisEventType,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Persist durable lifecycle event."""
        self._event_emitter.emit(event_type, payload)


class AnalysisOrchestrator:
    """Orchestrates background execution of an Analysis job across stages."""

    def __init__(
        self,
        *,
        analysis_repo: AnalysisRepository,
        job_repo: JobRepository,
        stage_repo: StageRepository,
        event_repo: EventRepository,
        diagnostic_repo: DiagnosticRepository,
        input_factory: AnalysisInputFactory,
        registry: StageHandlerRegistry,
        max_duration_seconds: int = DEFAULT_MAX_ANALYSIS_DURATION_SECONDS,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._job_repo = job_repo
        self._stage_repo = stage_repo
        self._event_repo = event_repo
        self._diagnostic_repo = diagnostic_repo
        self._input_factory = input_factory
        self._registry = registry
        self._max_duration_seconds = max_duration_seconds

    def execute(
        self,
        analysis_id: UUID,
        job_id: UUID,
        project_id: UUID,
        *,
        worker_id: str | None = None,
    ) -> None:
        """Execute the analysis job across its pipeline stages with state recovery."""
        analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
        job = self._job_repo.get_by_id(job_id)

        if analysis is None or job is None:
            raise AnalysisNotFoundError(
                message=f"Analysis '{analysis_id}' or job '{job_id}' not found.",
                details={"analysis_id": str(analysis_id), "job_id": str(job_id)},
            )

        # 1. Conditional Job Acquisition (Duplicate Delivery & Stale Worker Guard)
        if job.is_terminal:
            logger.info(
                "Job %s is already terminal (%s); skipping execution.",
                job_id,
                job.status,
            )
            return

        now = datetime.now(UTC)
        emitter = LifecycleEventEmitter(self._event_repo, analysis_id)

        # Transition Job to RUNNING
        if job.status != JobStatus.RUNNING:
            if not job.can_transition_to(JobStatus.RUNNING):
                logger.warning(
                    "Job %s cannot transition to RUNNING from %s.", job_id, job.status
                )
                return
            job = job.transition_to(
                JobStatus.RUNNING,
                updated_at=now,
                worker_id=worker_id or "worker-default",
                heartbeat_at=now,
                started_at=now,
            )
            self._job_repo.update(job, expected_version=job.version - 1)

        # Transition Analysis to RUNNING
        if analysis.status != AnalysisStatus.RUNNING:
            if analysis.status == AnalysisStatus.CREATED:
                analysis = analysis.transition_to(AnalysisStatus.QUEUED, updated_at=now)
                self._analysis_repo.update(
                    analysis, expected_version=analysis.version - 1
                )
                emitter.emit_queued(job_id)
            if analysis.can_transition_to(AnalysisStatus.RUNNING):
                analysis = analysis.transition_to(
                    AnalysisStatus.RUNNING,
                    updated_at=now,
                    started_at=now,
                )
                self._analysis_repo.update(
                    analysis, expected_version=analysis.version - 1
                )
                emitter.emit_started(job_id, worker_id)

        # 2. Construct immutable AnalysisInput
        input_data = self._input_factory.build_analysis_input(
            analysis_id=analysis.id,
            project_id=analysis.project_id,
            repository_id=analysis.repository_id,
            revision_id=analysis.snapshot_id,
            configuration=analysis.configuration,
        )

        stages = self._stage_repo.list_by_analysis(analysis_id)
        execution_start = job.started_at or now

        # 3. Stage Execution Loop
        has_warnings = False
        current_stage_id: UUID | None = None
        try:
            for stage in stages:
                current_stage_id = stage.id

                # A. Check cooperative cancellation
                analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
                if analysis and analysis.status == AnalysisStatus.CANCEL_REQUESTED:
                    raise AnalysisCancelledError(
                        "Cooperative cancellation checkpoint triggered."
                    )

                # B. Check 30-minute analysis timeout limit
                elapsed_seconds = (datetime.now(UTC) - execution_start).total_seconds()
                if elapsed_seconds > self._max_duration_seconds:
                    raise AnalysisTimeoutError(
                        f"Analysis exceeded maximum duration limit of "
                        f"{self._max_duration_seconds}s."
                    )

                # C. Check idempotent stage resumption
                if stage.is_terminal and stage.status == StageStatus.COMPLETED:
                    continue

                stage_now = datetime.now(UTC)

                # D. Transition Stage to RUNNING
                if stage.can_transition_to(StageStatus.RUNNING):
                    running_stage = stage.transition_to(
                        StageStatus.RUNNING,
                        updated_at=stage_now,
                        job_id=job.id,
                        started_at=stage_now,
                    )
                    self._stage_repo.update(
                        running_stage, expected_version=stage.version
                    )
                    stage = running_stage
                    emitter.emit_stage_started(stage.stage_name, stage.id, stage.order)

                # E. Retrieve Stage Handler from Registry
                handler: AnalysisStageHandler | None = self._registry.get(
                    stage.stage_name
                )
                if handler is None:
                    if stage.is_mandatory:
                        raise AnalysisConfigurationError(
                            f"Missing mandatory stage handler for stage "
                            f"'{stage.stage_name}'."
                        )
                    # Non-mandatory stage without handler -> SKIP
                    skipped_stage = stage.transition_to(
                        StageStatus.SKIPPED,
                        updated_at=datetime.now(UTC),
                    )
                    self._stage_repo.update(
                        skipped_stage, expected_version=stage.version
                    )
                    emitter.emit_stage_skipped(
                        stage.stage_name, stage.id, "No handler registered."
                    )
                    continue

                # F. Execute Handler
                ctx = _DefaultExecutionContext(
                    analysis_id=analysis_id,
                    project_id=project_id,
                    job_id=job.id,
                    stage_id=stage.id,
                    stage_name=stage.stage_name,
                    input_data=input_data,
                    analysis_repo=self._analysis_repo,
                    job_repo=self._job_repo,
                    stage_repo=self._stage_repo,
                    diagnostic_repo=self._diagnostic_repo,
                    event_emitter=emitter,
                )

                result = handler.execute(ctx)
                finish_now = datetime.now(UTC)

                # Reload latest stage state (heartbeat/progress updated version)
                latest_stage = self._stage_repo.get_by_id(stage.id) or stage

                # G. Process Stage Result
                if result.status == StageStatus.COMPLETED:
                    completed_stage = latest_stage.transition_to(
                        StageStatus.COMPLETED,
                        updated_at=finish_now,
                        processed_items=result.processed_items,
                        total_items=result.total_items,
                    )
                    self._stage_repo.update(
                        completed_stage, expected_version=latest_stage.version
                    )
                    emitter.emit_stage_completed(
                        latest_stage.stage_name,
                        latest_stage.id,
                        result.processed_items,
                        result.total_items,
                    )
                elif result.status == StageStatus.SKIPPED:
                    skipped_stage = latest_stage.transition_to(
                        StageStatus.SKIPPED,
                        updated_at=finish_now,
                        processed_items=result.processed_items,
                        total_items=result.total_items,
                    )
                    self._stage_repo.update(
                        skipped_stage, expected_version=latest_stage.version
                    )
                    emitter.emit_stage_skipped(
                        latest_stage.stage_name, latest_stage.id, result.error_message
                    )
                else:
                    # Stage reported failure
                    failed_stage = latest_stage.transition_to(
                        StageStatus.FAILED,
                        updated_at=finish_now,
                        processed_items=result.processed_items,
                        total_items=result.total_items,
                        error_code=result.error_code or "stage_failed",
                        error_message=result.error_message or "Stage reported failure.",
                    )
                    self._stage_repo.update(
                        failed_stage, expected_version=latest_stage.version
                    )
                    emitter.emit_stage_failed(
                        latest_stage.stage_name,
                        latest_stage.id,
                        result.error_code,
                        result.error_message,
                    )

                    if latest_stage.is_mandatory:
                        self._handle_terminal_failure(
                            analysis_id=analysis_id,
                            project_id=project_id,
                            job_id=job_id,
                            error_code=result.error_code or "stage_failed",
                            error_message=result.error_message
                            or f"Mandatory stage '{latest_stage.stage_name}' failed.",
                            emitter=emitter,
                        )
                        return
                    has_warnings = True

            # 4. All stages completed successfully -> Terminal Analysis Success
            complete_now = datetime.now(UTC)
            final_status = (
                AnalysisStatus.COMPLETED_WITH_WARNINGS
                if has_warnings
                else AnalysisStatus.COMPLETED
            )
            latest_analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
            if latest_analysis and latest_analysis.can_transition_to(final_status):
                completed_analysis = latest_analysis.transition_to(
                    final_status,
                    updated_at=complete_now,
                    completed_at=complete_now,
                )
                self._analysis_repo.update(
                    completed_analysis, expected_version=latest_analysis.version
                )

            latest_job = self._job_repo.get_by_id(job_id)
            if latest_job and latest_job.can_transition_to(JobStatus.COMPLETED):
                completed_job = latest_job.transition_to(
                    JobStatus.COMPLETED,
                    updated_at=complete_now,
                    completed_at=complete_now,
                )
                self._job_repo.update(
                    completed_job, expected_version=latest_job.version
                )

            emitter.emit_completed(with_warnings=has_warnings)

        except AnalysisCancelledError as exc:
            self._handle_cancellation(
                analysis_id=analysis_id,
                project_id=project_id,
                job_id=job_id,
                current_stage_id=current_stage_id,
                reason=str(exc),
                emitter=emitter,
            )
        except AnalysisTimeoutError as exc:
            self._handle_timeout(
                analysis_id=analysis_id,
                project_id=project_id,
                job_id=job_id,
                current_stage_id=current_stage_id,
                reason=str(exc),
                emitter=emitter,
            )
        except Exception as exc:
            logger.exception("Unexpected error in analysis execution: %s", exc)
            self._handle_terminal_failure(
                analysis_id=analysis_id,
                project_id=project_id,
                job_id=job_id,
                error_code="execution_error",
                error_message=str(exc),
                emitter=emitter,
            )

    def _handle_terminal_failure(
        self,
        *,
        analysis_id: UUID,
        project_id: UUID,
        job_id: UUID,
        error_code: str,
        error_message: str,
        emitter: LifecycleEventEmitter,
    ) -> None:
        """Mark Analysis and Job as FAILED."""
        now = datetime.now(UTC)
        analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
        if (
            analysis
            and not analysis.is_terminal
            and analysis.can_transition_to(AnalysisStatus.FAILED)
        ):
            failed_analysis = analysis.transition_to(
                AnalysisStatus.FAILED,
                updated_at=now,
                completed_at=now,
                error_code=error_code,
                error_message=error_message,
            )
            self._analysis_repo.update(
                failed_analysis, expected_version=analysis.version
            )

        job = self._job_repo.get_by_id(job_id)
        if job and not job.is_terminal and job.can_transition_to(JobStatus.FAILED):
            failed_job = job.transition_to(
                JobStatus.FAILED,
                updated_at=now,
                completed_at=now,
                error_code=error_code,
                error_message=error_message,
            )
            self._job_repo.update(failed_job, expected_version=job.version)

        emitter.emit_failed(error_code, error_message)

    def _handle_cancellation(
        self,
        *,
        analysis_id: UUID,
        project_id: UUID,
        job_id: UUID,
        current_stage_id: UUID | None,
        reason: str,
        emitter: LifecycleEventEmitter,
    ) -> None:
        """Process cooperative cancellation transition."""
        now = datetime.now(UTC)

        # Mark current stage as CANCELLED if running
        if current_stage_id:
            stage = self._stage_repo.get_by_id(current_stage_id)
            if (
                stage
                and not stage.is_terminal
                and stage.can_transition_to(StageStatus.CANCELLED)
            ):
                cancelled_stage = stage.transition_to(
                    StageStatus.CANCELLED,
                    updated_at=now,
                    completed_at=now,
                    error_message=reason,
                )
                self._stage_repo.update(cancelled_stage, expected_version=stage.version)

        analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
        if (
            analysis
            and not analysis.is_terminal
            and analysis.can_transition_to(AnalysisStatus.CANCELLED)
        ):
            cancelled_analysis = analysis.transition_to(
                AnalysisStatus.CANCELLED,
                updated_at=now,
                completed_at=now,
                error_message=reason,
            )
            self._analysis_repo.update(
                cancelled_analysis, expected_version=analysis.version
            )

        job = self._job_repo.get_by_id(job_id)
        if job and not job.is_terminal and job.can_transition_to(JobStatus.CANCELLED):
            cancelled_job = job.transition_to(
                JobStatus.CANCELLED,
                updated_at=now,
                completed_at=now,
                error_message=reason,
            )
            self._job_repo.update(cancelled_job, expected_version=job.version)

        emitter.emit_cancelled(reason)

    def _handle_timeout(
        self,
        *,
        analysis_id: UUID,
        project_id: UUID,
        job_id: UUID,
        current_stage_id: UUID | None,
        reason: str,
        emitter: LifecycleEventEmitter,
    ) -> None:
        """Process execution timeout transition (RUNNING -> TIMEOUT -> FAILED)."""
        now = datetime.now(UTC)

        if current_stage_id:
            stage = self._stage_repo.get_by_id(current_stage_id)
            if (
                stage
                and not stage.is_terminal
                and stage.can_transition_to(StageStatus.FAILED)
            ):
                failed_stage = stage.transition_to(
                    StageStatus.FAILED,
                    updated_at=now,
                    completed_at=now,
                    error_code="stage_timeout",
                    error_message="Stage exceeded maximum execution time.",
                )
                self._stage_repo.update(failed_stage, expected_version=stage.version)

        analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
        if (
            analysis
            and not analysis.is_terminal
            and analysis.can_transition_to(AnalysisStatus.TIMEOUT)
        ):
            timeout_analysis = analysis.transition_to(
                AnalysisStatus.TIMEOUT,
                updated_at=now,
            )
            failed_analysis = timeout_analysis.transition_to(
                AnalysisStatus.FAILED,
                updated_at=now,
                completed_at=now,
                error_code="analysis_timeout",
                error_message=reason,
            )
            self._analysis_repo.update(
                failed_analysis, expected_version=analysis.version
            )

        job = self._job_repo.get_by_id(job_id)
        if job and not job.is_terminal and job.can_transition_to(JobStatus.FAILED):
            failed_job = job.transition_to(
                JobStatus.FAILED,
                updated_at=now,
                completed_at=now,
                error_code="analysis_timeout",
                error_message=reason,
            )
            self._job_repo.update(failed_job, expected_version=job.version)

        emitter.emit_timeout(self._max_duration_seconds)
        emitter.emit_failed("analysis_timeout", reason)
