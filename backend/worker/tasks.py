"""Celery task definitions for executing background analysis jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.platform.analysis.application.handoff import AnalysisAttemptStore
from backend.platform.analysis.application.input_factory import (
    PlatformAnalysisInputFactory,
)
from backend.platform.analysis.application.orchestrator import AnalysisOrchestrator
from backend.platform.analysis.application.platform_gateway import (
    HttpPlatformRepositoryGateway,
)
from backend.platform.analysis.application.recovery import JobRecoveryService
from backend.platform.analysis.application.registry import (
    StageHandlerRegistry,
)
from backend.platform.analysis.domain.constants import JobStatus
from backend.platform.analysis.infra.analysis_repository import (
    SqlAlchemyAnalysisRepository,
)
from backend.platform.analysis.infra.diagnostic_repository import (
    SqlAlchemyDiagnosticRepository,
)
from backend.platform.analysis.infra.event_repository import (
    SqlAlchemyEventRepository,
)
from backend.platform.analysis.infra.job_repository import (
    SqlAlchemyJobRepository,
    SqlAlchemyStageRepository,
)
from backend.platform.analysis.infra.queue import CeleryAnalysisQueuePublisher
from backend.platform.analysis.inspection.handlers import (
    M2ExecutionCoordinator,
    register_m2_stage_handlers,
)
from backend.platform.analysis.ir.handlers import register_ir_stage_handler
from backend.platform.config import get_settings
from backend.platform.dependency_injection import get_database_engine
from backend.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_registry_instance: StageHandlerRegistry | None = None
_m2_coordinator_instance: M2ExecutionCoordinator | None = None
_attempt_store_instance: AnalysisAttemptStore | None = None


def get_worker_registry() -> StageHandlerRegistry:
    """Return registered production handlers; never fabricate analysis results."""
    global _registry_instance, _m2_coordinator_instance, _attempt_store_instance
    if _registry_instance is None:
        _registry_instance = StageHandlerRegistry()
        _m2_coordinator_instance = M2ExecutionCoordinator()
        register_m2_stage_handlers(_registry_instance, _m2_coordinator_instance)

        _attempt_store_instance = AnalysisAttemptStore(
            m2_handoff=_m2_coordinator_instance.handoff
        )
        register_ir_stage_handler(
            _registry_instance,
            f2_reader=_attempt_store_instance,
            f3_writer=_attempt_store_instance,
        )
    return _registry_instance


def get_m2_coordinator() -> M2ExecutionCoordinator:
    """Return the production M2 composition for handoff/recovery integration."""
    get_worker_registry()
    assert _m2_coordinator_instance is not None
    return _m2_coordinator_instance


def get_attempt_store() -> AnalysisAttemptStore:
    """Return the production attempt store for F2/F3 handoff integration."""
    get_worker_registry()
    assert _attempt_store_instance is not None
    return _attempt_store_instance


def set_worker_registry(registry: StageHandlerRegistry | None) -> None:
    """Set the worker registry instance for testing or M2-M4 registration."""
    global _registry_instance, _m2_coordinator_instance, _attempt_store_instance
    _registry_instance = registry
    _m2_coordinator_instance = None
    _attempt_store_instance = None


@celery_app.task(
    bind=True,
    name="stacksense.execute_analysis",
    max_retries=get_settings().analysis_max_retries,
    soft_time_limit=get_settings().analysis_max_duration_seconds,
    time_limit=get_settings().analysis_max_duration_seconds + 30,
)
def execute_analysis_task(
    self: Task,
    analysis_id: str,
    job_id: str,
    project_id: str,
    **kwargs: Any,
) -> None:
    """Execute background analysis job task."""
    logger.info(
        "Celery worker received execution task for analysis %s, job %s (kwargs: %s)",
        analysis_id,
        job_id,
        list(kwargs.keys()),
    )
    engine = get_database_engine()
    settings = get_settings()

    try:
        with Session(engine) as session:
            analysis_repo = SqlAlchemyAnalysisRepository(session)
            job_repo = SqlAlchemyJobRepository(session)
            stage_repo = SqlAlchemyStageRepository(session)
            event_repo = SqlAlchemyEventRepository(session)
            diagnostic_repo = SqlAlchemyDiagnosticRepository(session)
            input_factory = PlatformAnalysisInputFactory(
                HttpPlatformRepositoryGateway(
                    settings.platform_api_base_url,
                    settings.platform_api_secret_key.get_secret_value(),
                    settings.platform_api_timeout_seconds,
                )
            )

            orchestrator = AnalysisOrchestrator(
                analysis_repo=analysis_repo,
                job_repo=job_repo,
                stage_repo=stage_repo,
                event_repo=event_repo,
                diagnostic_repo=diagnostic_repo,
                input_factory=input_factory,
                registry=get_worker_registry(),
                max_duration_seconds=settings.analysis_max_duration_seconds,
                stage_timeout_seconds=settings.analysis_stage_timeout_seconds,
                max_diagnostics=settings.analysis_max_diagnostics_per_analysis,
                checkpoint=session.commit,
            )

            hostname = getattr(self.request, "hostname", None) or "worker-celery"
            orchestrator.execute(
                analysis_id=UUID(analysis_id),
                job_id=UUID(job_id),
                project_id=UUID(project_id),
                worker_id=hostname,
            )
            session.commit()
    except OperationalError as exc:
        # Make the next Celery delivery acquirable when the previous worker had
        # already committed RUNNING before the transient database failure.
        try:
            with Session(engine) as recovery_session:
                recovery_repo = SqlAlchemyJobRepository(recovery_session)
                failed_attempt = recovery_repo.get_by_id(UUID(job_id))
                if failed_attempt and failed_attempt.status == JobStatus.RUNNING:
                    retrying = failed_attempt.transition_to(
                        JobStatus.RETRYING,
                        updated_at=datetime.now(UTC),
                        error_code="transient_infrastructure_failure",
                        error_message="Worker will retry after a transient failure.",
                        increment_attempt=True,
                    )
                    recovery_repo.update(
                        retrying, expected_version=failed_attempt.version
                    )
                    recovery_session.commit()
        except Exception:
            logger.exception("Could not persist retry state for job %s", job_id)
        raise self.retry(
            exc=exc,
            countdown=settings.analysis_retry_backoff_seconds,
        ) from exc


@celery_app.task(name="stacksense.recover_analysis_jobs")
def recover_analysis_jobs_task() -> None:
    """Periodically republish undispatched and stale analysis jobs."""
    engine = get_database_engine()
    settings = get_settings()
    now = datetime.now(UTC)
    with Session(engine) as session:
        analysis_repo = SqlAlchemyAnalysisRepository(session)
        job_repo = SqlAlchemyJobRepository(session)
        recovery = JobRecoveryService(
            analysis_repo=analysis_repo,
            job_repo=job_repo,
            event_repo=SqlAlchemyEventRepository(session),
            diagnostic_repo=SqlAlchemyDiagnosticRepository(session),
            queue_publisher=CeleryAnalysisQueuePublisher(
                queue_name=settings.analysis_queue_name
            ),
            checkpoint=session.commit,
        )
        pending_cutoff = now - timedelta(
            seconds=settings.analysis_dispatch_recovery_interval_seconds
        )
        for job in job_repo.find_pending_jobs(pending_cutoff):
            recovery.recover_undispatched_job(
                job.analysis_id,
                job.project_id,
                threshold_seconds=settings.analysis_dispatch_recovery_interval_seconds,
            )
            session.commit()

        stale_cutoff = now - timedelta(
            seconds=settings.analysis_stale_job_threshold_seconds
        )
        for job in job_repo.find_stale_jobs(stale_cutoff):
            recovery.check_and_recover_stale_job(
                job.id,
                threshold_seconds=settings.analysis_stale_job_threshold_seconds,
            )
            session.commit()
