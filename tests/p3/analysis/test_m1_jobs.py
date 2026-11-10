"""Tests for Celery tasks, stale job detection, retries, and recovery."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.platform.analysis.application.dto import CreateAnalysisRequest
from backend.platform.analysis.application.lifecycle_service import (
    AnalysisLifecycleService,
)
from backend.platform.analysis.application.recovery import (
    JobRecoveryService,
)
from backend.platform.analysis.domain.constants import (
    AnalysisStatus,
    JobStatus,
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
from backend.platform.analysis.infra.lifecycle_model import (
    AnalysisDiagnosticModel,
    AnalysisEventModel,
    AnalysisJobModel,
    AnalysisModel,
    AnalysisStageModel,
)
from backend.platform.analysis.infra.queue import (
    InMemoryAnalysisQueuePublisher,
)
from backend.platform.ingestion.infra.model import (
    ArtifactModel,
    IngestionModel,
    RevisionModel,
)
from backend.platform.ingestion.infra.revision_repository import (
    SqlAlchemyRevisionRepository,
)
from backend.platform.projects.domain.project import Project
from backend.platform.projects.infra.base import Base
from backend.platform.projects.infra.model import ProjectModel
from backend.platform.projects.infra.repository import (
    SqlAlchemyProjectRepository,
)
from backend.platform.repositories.domain.repository import Repository
from backend.platform.repositories.infra.model import RepositoryModel
from backend.platform.repositories.infra.repository import (
    SqlAlchemyRepositoryRepository,
)


@pytest.fixture
def session() -> Generator[Session]:
    _ = (
        ProjectModel,
        RepositoryModel,
        IngestionModel,
        RevisionModel,
        ArtifactModel,
        AnalysisModel,
        AnalysisJobModel,
        AnalysisStageModel,
        AnalysisEventModel,
        AnalysisDiagnosticModel,
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    sess = session_factory()
    try:
        yield sess
        sess.commit()
    finally:
        sess.close()
        engine.dispose()


def _setup_fixtures(session: Session) -> tuple[Project, Repository, RevisionModel]:
    now = datetime.now(UTC)
    project_repo = SqlAlchemyProjectRepository(session)
    repo_repo = SqlAlchemyRepositoryRepository(session)

    project = Project(
        id=uuid4(),
        name="test-project",
        description="Test project",
        created_at=now,
        updated_at=now,
    )
    project_repo.save(project)

    repository = Repository(
        id=uuid4(),
        project_id=project.id,
        name="backend-repo",
        description="Main backend",
        status="registered",
        created_at=now,
        updated_at=now,
    )
    repo_repo.save(repository)

    rev_model = RevisionModel(
        id=uuid4(),
        project_id=project.id,
        repository_id=repository.id,
        revision_identifier="commit-100",
        source_hash="sha-tree-100",
        total_files=0,
        total_bytes=0,
        created_at=now,
    )
    session.add(rev_model)
    session.flush()

    return project, repository, rev_model


def _build_services(
    session: Session,
) -> tuple[
    AnalysisLifecycleService, JobRecoveryService, InMemoryAnalysisQueuePublisher
]:
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    job_repo = SqlAlchemyJobRepository(session)
    stage_repo = SqlAlchemyStageRepository(session)
    event_repo = SqlAlchemyEventRepository(session)
    diagnostic_repo = SqlAlchemyDiagnosticRepository(session)
    revision_repo = SqlAlchemyRevisionRepository(session)
    project_repo = SqlAlchemyProjectRepository(session)
    repository_repo = SqlAlchemyRepositoryRepository(session)
    publisher = InMemoryAnalysisQueuePublisher()

    lifecycle_service = AnalysisLifecycleService(
        analysis_repo=analysis_repo,
        job_repo=job_repo,
        stage_repo=stage_repo,
        event_repo=event_repo,
        diagnostic_repo=diagnostic_repo,
        revision_repo=revision_repo,
        project_repo=project_repo,
        repository_repo=repository_repo,
    )

    recovery_service = JobRecoveryService(
        analysis_repo=analysis_repo,
        job_repo=job_repo,
        event_repo=event_repo,
        diagnostic_repo=diagnostic_repo,
        queue_publisher=publisher,
    )

    return lifecycle_service, recovery_service, publisher


def test_recovery_of_undispatched_job(session: Session) -> None:
    project, repo, rev = _setup_fixtures(session)
    lifecycle_service, recovery_service, publisher = _build_services(session)

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    # Manually backdate job created_at by 100 seconds to simulate dispatch failure
    job_repo = SqlAlchemyJobRepository(session)
    job = job_repo.get_by_id(created.active_job.id)
    assert job is not None
    past_time = datetime.now(UTC) - timedelta(seconds=100)
    backdated = AnalysisJobModel(
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
        created_at=past_time,
        updated_at=past_time,
    )
    session.merge(backdated)
    session.flush()

    # Recover
    recovered = recovery_service.recover_undispatched_job(
        created.id, project.id, threshold_seconds=60
    )
    assert recovered is True
    assert len(publisher.published_jobs) == 1
    assert publisher.published_jobs[0].analysis_id == created.id

    # Verify analysis is transitioned to QUEUED
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    updated_analysis = analysis_repo.get_by_id(created.id, project.id)
    assert updated_analysis is not None
    assert updated_analysis.status == AnalysisStatus.QUEUED


def test_recovery_republishes_queued_job_without_worker_lease(session: Session) -> None:
    project, repo, rev = _setup_fixtures(session)
    lifecycle_service, recovery_service, publisher = _build_services(session)
    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    job_repo = SqlAlchemyJobRepository(session)
    pending = job_repo.get_by_id(created.active_job.id)
    assert pending is not None
    queued = pending.transition_to(JobStatus.QUEUED, updated_at=datetime.now(UTC))
    job_repo.update(queued, expected_version=pending.version)
    model = session.get(AnalysisJobModel, queued.id)
    assert model is not None
    model.created_at = datetime.now(UTC) - timedelta(seconds=100)
    session.flush()
    assert [item.id for item in job_repo.find_pending_jobs(datetime.now(UTC))] == [
        queued.id
    ]

    recovered = recovery_service.recover_undispatched_job(
        created.id, project.id, threshold_seconds=60
    )

    assert recovered is True
    assert len(publisher.published_jobs) == 1
    recovered_job = job_repo.get_by_id(queued.id)
    assert recovered_job is not None
    assert recovered_job.status == JobStatus.QUEUED
    assert recovered_job.worker_id is None


def test_recovery_of_undispatched_job_ignores_recent_job(session: Session) -> None:
    project, repo, rev = _setup_fixtures(session)
    lifecycle_service, recovery_service, publisher = _build_services(session)

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )

    # Threshold 60s, job created just now -> not recovered
    recovered = recovery_service.recover_undispatched_job(
        created.id, project.id, threshold_seconds=60
    )
    assert recovered is False
    assert len(publisher.published_jobs) == 0


def test_recovery_of_stale_job_with_retries_remaining(session: Session) -> None:
    project, repo, rev = _setup_fixtures(session)
    lifecycle_service, recovery_service, publisher = _build_services(session)

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    job_repo = SqlAlchemyJobRepository(session)
    job = job_repo.get_by_id(created.active_job.id)
    assert job is not None

    # Advance job to RUNNING with old heartbeat
    old_heartbeat = datetime.now(UTC) - timedelta(seconds=200)
    running_job = job.transition_to(
        JobStatus.RUNNING,
        updated_at=old_heartbeat,
        heartbeat_at=old_heartbeat,
        started_at=old_heartbeat,
        worker_id="crashed-worker",
    )
    job_repo.update(running_job, expected_version=job.version)

    # Recover stale job (attempt 1 < 3) -> RETRYING
    recovered = recovery_service.check_and_recover_stale_job(
        created.active_job.id, threshold_seconds=120
    )
    assert recovered is True

    updated_job = job_repo.get_by_id(created.active_job.id)
    assert updated_job is not None
    assert updated_job.status == JobStatus.RETRYING
    assert updated_job.attempt == 2
    assert len(publisher.published_jobs) == 1


def test_recovery_of_stale_job_exhausted_retries_marks_failed(session: Session) -> None:
    project, repo, rev = _setup_fixtures(session)
    lifecycle_service, recovery_service, publisher = _build_services(session)

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    job_repo = SqlAlchemyJobRepository(session)
    job = job_repo.get_by_id(created.active_job.id)
    assert job is not None

    # Set attempt = 3 (max_attempts = 3) and old heartbeat
    old_heartbeat = datetime.now(UTC) - timedelta(seconds=200)
    running_job = job.transition_to(
        JobStatus.RUNNING,
        updated_at=old_heartbeat,
        heartbeat_at=old_heartbeat,
        started_at=old_heartbeat,
    )
    job_repo.update(running_job, expected_version=job.version)

    # Increment attempt to 3
    model = session.get(AnalysisJobModel, job.id)
    assert model is not None
    model.attempt = 3
    session.flush()

    # Recover stale job with attempts exhausted -> FAILED
    recovered = recovery_service.check_and_recover_stale_job(
        created.active_job.id, threshold_seconds=120
    )
    assert recovered is True

    failed_job = job_repo.get_by_id(created.active_job.id)
    assert failed_job is not None
    assert failed_job.status == JobStatus.FAILED
    assert failed_job.error_code == "stale_worker_lost"

    analysis_repo = SqlAlchemyAnalysisRepository(session)
    failed_analysis = analysis_repo.get_by_id(created.id, project.id)
    assert failed_analysis is not None
    assert failed_analysis.status == AnalysisStatus.FAILED


def test_stale_job_recovery_ignores_healthy_heartbeat(session: Session) -> None:
    project, repo, rev = _setup_fixtures(session)
    lifecycle_service, recovery_service, publisher = _build_services(session)

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    job_repo = SqlAlchemyJobRepository(session)
    job = job_repo.get_by_id(created.active_job.id)
    assert job is not None

    now = datetime.now(UTC)
    running_job = job.transition_to(
        JobStatus.RUNNING,
        updated_at=now,
        heartbeat_at=now,
        started_at=now,
    )
    job_repo.update(running_job, expected_version=job.version)

    # Healthy heartbeat -> not recovered
    recovered = recovery_service.check_and_recover_stale_job(
        created.active_job.id, threshold_seconds=120
    )
    assert recovered is False
    assert len(publisher.published_jobs) == 0
