"""Recovery service for undispatched and stale/orphan background jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.platform.analysis.application.events import LifecycleEventEmitter
from backend.platform.analysis.domain.constants import (
    AnalysisStatus,
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
    JobStatus,
)
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.infra.queue import (
    AnalysisJobPayload,
    AnalysisQueuePublisher,
)
from backend.platform.analysis.repositories.analysis_repo import AnalysisRepository
from backend.platform.analysis.repositories.diagnostic_repo import DiagnosticRepository
from backend.platform.analysis.repositories.event_repo import EventRepository
from backend.platform.analysis.repositories.job_repo import JobRepository

logger = logging.getLogger(__name__)


class JobRecoveryService:
    """Service detecting and recovering undispatched jobs and dead-worker orphans."""

    def __init__(
        self,
        *,
        analysis_repo: AnalysisRepository,
        job_repo: JobRepository,
        event_repo: EventRepository,
        diagnostic_repo: DiagnosticRepository,
        queue_publisher: AnalysisQueuePublisher,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._job_repo = job_repo
        self._event_repo = event_repo
        self._diagnostic_repo = diagnostic_repo
        self._queue_publisher = queue_publisher

    def recover_undispatched_job(
        self,
        analysis_id: UUID,
        project_id: UUID,
        *,
        threshold_seconds: int = 60,
    ) -> bool:
        """Attempt to republish an undispatched job for an analysis."""
        analysis = self._analysis_repo.get_by_id(analysis_id, project_id)
        if analysis is None or analysis.is_terminal:
            return False

        active_job = self._job_repo.get_active_for_analysis(analysis_id)
        if active_job is None or active_job.status != JobStatus.PENDING:
            return False

        now = datetime.now(UTC)
        age_seconds = (now - active_job.created_at).total_seconds()
        if age_seconds < threshold_seconds:
            return False

        logger.info(
            "Recovering undispatched job %s for analysis %s (age %0.1fs).",
            active_job.id,
            analysis_id,
            age_seconds,
        )

        payload = AnalysisJobPayload(
            analysis_id=analysis.id,
            job_id=active_job.id,
            project_id=analysis.project_id,
        )
        self._queue_publisher.publish_job(payload)

        # Transition to QUEUED if still CREATED
        if analysis.status == AnalysisStatus.CREATED:
            updated_analysis = analysis.transition_to(
                AnalysisStatus.QUEUED,
                updated_at=now,
            )
            self._analysis_repo.update(
                updated_analysis, expected_version=analysis.version
            )
            emitter = LifecycleEventEmitter(self._event_repo, analysis.id)
            emitter.emit_queued(active_job.id)

        return True

    def check_and_recover_stale_job(
        self,
        job_id: UUID,
        *,
        threshold_seconds: int = 120,
    ) -> bool:
        """Check if a running job has lost heartbeat and recover it."""
        job = self._job_repo.get_by_id(job_id)
        if job is None or job.status != JobStatus.RUNNING:
            return False

        now = datetime.now(UTC)
        heartbeat = job.heartbeat_at or job.started_at or job.created_at
        age_seconds = (now - heartbeat).total_seconds()
        if age_seconds < threshold_seconds:
            return False

        logger.warning(
            "Detected stale/orphan job %s (last heartbeat %0.1fs ago).",
            job.id,
            age_seconds,
        )

        analysis = self._analysis_repo.get_by_id(job.analysis_id, job.project_id)
        emitter = LifecycleEventEmitter(self._event_repo, job.analysis_id)

        # Retry if attempts remain
        if job.attempt < job.max_attempts:
            retrying_job = job.transition_to(
                JobStatus.RETRYING,
                updated_at=now,
                error_code="stale_worker_heartbeat_lost",
                error_message=f"Worker heartbeat timed out after {age_seconds:.0f}s.",
                increment_attempt=True,
            )
            self._job_repo.update(retrying_job, expected_version=job.version)

            payload = AnalysisJobPayload(
                analysis_id=job.analysis_id,
                job_id=job.id,
                project_id=job.project_id,
            )
            self._queue_publisher.publish_job(payload)
            logger.info(
                "Republished retried job %s for analysis %s.", job.id, job.analysis_id
            )
            return True

        # Retries exhausted -> mark FAILED
        failed_job = job.transition_to(
            JobStatus.FAILED,
            updated_at=now,
            completed_at=now,
            error_code="stale_worker_lost",
            error_message=(
                f"Worker heartbeat lost after {age_seconds:.0f}s; "
                "max attempts exceeded."
            ),
        )
        self._job_repo.update(failed_job, expected_version=job.version)

        if analysis and not analysis.is_terminal:
            failed_analysis = analysis.transition_to(
                AnalysisStatus.FAILED,
                updated_at=now,
                completed_at=now,
                error_code="stale_worker_lost",
                error_message="Background analysis worker became unreachable.",
            )
            self._analysis_repo.update(
                failed_analysis, expected_version=analysis.version
            )

        # Record orphan diagnostic
        diag = AnalysisDiagnostic(
            id=uuid4(),
            analysis_id=job.analysis_id,
            job_id=job.id,
            code="stale_worker_lost",
            category=DiagnosticCategory.INFRASTRUCTURE,
            severity=DiagnosticSeverity.ERROR,
            scope=DiagnosticScope.JOB,
            message="Worker heartbeat lost and retry budget exhausted.",
            retryability=FailureRetryability.NON_RETRYABLE,
            created_at=now,
            details={"stale_seconds": age_seconds, "worker_id": job.worker_id},
        )
        self._diagnostic_repo.save_batch([diag])
        emitter.emit_failed("stale_worker_lost", "Worker heartbeat lost.")
        return True
