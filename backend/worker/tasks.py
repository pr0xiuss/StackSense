"""Celery task definitions for executing background analysis jobs."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session

from backend.platform.analysis.application.input_factory import AnalysisInputFactory
from backend.platform.analysis.application.orchestrator import AnalysisOrchestrator
from backend.platform.analysis.application.registry import (
    StageHandlerRegistry,
    create_fake_handler_registry,
)
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
from backend.platform.config import get_settings
from backend.platform.dependency_injection import get_database_engine
from backend.platform.ingestion.infra.artifact_repository import (
    SqlAlchemyArtifactRepository,
)
from backend.platform.ingestion.infra.revision_repository import (
    SqlAlchemyRevisionRepository,
)
from backend.platform.ingestion.infra.storage.local_storage import (
    LocalStorageService,
)
from backend.platform.repositories.infra.repository import (
    SqlAlchemyRepositoryRepository,
)
from backend.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_registry_instance: StageHandlerRegistry | None = None


def get_worker_registry() -> StageHandlerRegistry:
    """Return the active StageHandlerRegistry, defaulting to fake handlers in M1."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = create_fake_handler_registry()
    return _registry_instance


def set_worker_registry(registry: StageHandlerRegistry | None) -> None:
    """Set the worker registry instance for testing or M2-M4 registration."""
    global _registry_instance
    _registry_instance = registry


@celery_app.task(bind=True, name="stacksense.execute_analysis", max_retries=3)
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

    with Session(engine) as session:
        analysis_repo = SqlAlchemyAnalysisRepository(session)
        job_repo = SqlAlchemyJobRepository(session)
        stage_repo = SqlAlchemyStageRepository(session)
        event_repo = SqlAlchemyEventRepository(session)
        diagnostic_repo = SqlAlchemyDiagnosticRepository(session)
        revision_repo = SqlAlchemyRevisionRepository(session)
        artifact_repo = SqlAlchemyArtifactRepository(session)
        repository_repo = SqlAlchemyRepositoryRepository(session)

        storage_service = LocalStorageService(settings.storage_root)

        input_factory = AnalysisInputFactory(
            revision_repo=revision_repo,
            artifact_repo=artifact_repo,
            storage_service=storage_service,
            repository_repo=repository_repo,
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
        )

        hostname = getattr(self.request, "hostname", None) or "worker-celery"
        orchestrator.execute(
            analysis_id=UUID(analysis_id),
            job_id=UUID(job_id),
            project_id=UUID(project_id),
            worker_id=hostname,
        )
        session.commit()
