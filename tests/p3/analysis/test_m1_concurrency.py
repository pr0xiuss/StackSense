"""Concurrency, optimistic locking, and conflict tests for M1 repositories."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.platform.analysis.domain.analysis import (
    Analysis,
    AnalysisConfiguration,
)
from backend.platform.analysis.domain.constants import (
    AnalysisStatus,
    JobStatus,
    StageStatus,
)
from backend.platform.analysis.domain.job import AnalysisJob, AnalysisStage
from backend.platform.analysis.infra.analysis_repository import (
    SqlAlchemyAnalysisRepository,
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
from backend.platform.errors import AnalysisStateConflictError
from backend.platform.ingestion.infra.model import (
    ArtifactModel,
    IngestionModel,
    RevisionModel,
)
from backend.platform.projects.infra.base import Base
from backend.platform.projects.infra.model import ProjectModel
from backend.platform.repositories.infra.model import RepositoryModel


@pytest.fixture
def session() -> Generator[Session]:
    """Provide an isolated in-memory SQLite session with all tables created."""
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


def _setup_entities(
    session: Session,
) -> tuple[ProjectModel, RepositoryModel, RevisionModel]:
    now = datetime.now(UTC)
    project = ProjectModel(
        id=uuid4(),
        name="test-project",
        description="Test project",
        created_at=now,
        updated_at=now,
    )
    repo = RepositoryModel(
        id=uuid4(),
        project_id=project.id,
        name="test-repo",
        description="Test repository",
        status="registered",
        created_at=now,
        updated_at=now,
    )
    rev = RevisionModel(
        id=uuid4(),
        project_id=project.id,
        repository_id=repo.id,
        revision_identifier="commit-1",
        source_hash="hash-1",
        total_files=0,
        total_bytes=0,
        created_at=now,
    )
    session.add_all([project, repo, rev])
    session.flush()
    return project, repo, rev


def test_concurrent_analysis_transition_collision(session: Session) -> None:
    project, repo, rev = _setup_entities(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)

    now = datetime.now(UTC)
    analysis = Analysis(
        id=uuid4(),
        project_id=project.id,
        repository_id=repo.id,
        snapshot_id=rev.id,
        status=AnalysisStatus.CREATED,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )
    analysis_repo.save(analysis)

    # Worker 1 reads analysis at version 1
    worker1_analysis = analysis_repo.get_by_id(analysis.id, project.id)
    assert worker1_analysis is not None
    assert worker1_analysis.version == 1

    # Worker 2 reads analysis at version 1
    worker2_analysis = analysis_repo.get_by_id(analysis.id, project.id)
    assert worker2_analysis is not None
    assert worker2_analysis.version == 1

    # Worker 1 transitions CREATED -> QUEUED and saves (increments version to 2)
    w1_updated = worker1_analysis.transition_to(
        AnalysisStatus.QUEUED,
        updated_at=datetime.now(UTC),
    )
    analysis_repo.update(w1_updated, expected_version=1)

    # Worker 2 attempts transition CREATED -> FAILED with expected_version=1
    w2_updated = worker2_analysis.transition_to(
        AnalysisStatus.FAILED,
        updated_at=datetime.now(UTC),
    )
    with pytest.raises(AnalysisStateConflictError) as exc_info:
        analysis_repo.update(w2_updated, expected_version=1)

    assert "Concurrency conflict" in str(exc_info.value.message)


def test_concurrent_job_update_collision(session: Session) -> None:
    project, repo, rev = _setup_entities(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    job_repo = SqlAlchemyJobRepository(session)

    now = datetime.now(UTC)
    analysis = Analysis(
        id=uuid4(),
        project_id=project.id,
        repository_id=repo.id,
        snapshot_id=rev.id,
        status=AnalysisStatus.CREATED,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )
    analysis_repo.save(analysis)

    job = AnalysisJob(
        id=uuid4(),
        analysis_id=analysis.id,
        project_id=project.id,
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    job_repo.save(job)

    # Both workers read job at version 1
    w1_job = job_repo.get_by_id(job.id)
    w2_job = job_repo.get_by_id(job.id)
    assert w1_job is not None and w2_job is not None

    # Worker 1 acquires job: PENDING -> RUNNING
    w1_updated = w1_job.transition_to(
        JobStatus.RUNNING,
        updated_at=datetime.now(UTC),
        worker_id="worker-1",
    )
    job_repo.update(w1_updated, expected_version=1)

    # Worker 2 attempts update on stale version
    w2_updated = w2_job.transition_to(
        JobStatus.RUNNING,
        updated_at=datetime.now(UTC),
        worker_id="worker-2",
    )
    with pytest.raises(AnalysisStateConflictError):
        job_repo.update(w2_updated, expected_version=1)


def test_concurrent_stage_update_collision(session: Session) -> None:
    project, repo, rev = _setup_entities(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    stage_repo = SqlAlchemyStageRepository(session)

    now = datetime.now(UTC)
    analysis = Analysis(
        id=uuid4(),
        project_id=project.id,
        repository_id=repo.id,
        snapshot_id=rev.id,
        status=AnalysisStatus.CREATED,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )
    analysis_repo.save(analysis)

    stage = AnalysisStage(
        id=uuid4(),
        analysis_id=analysis.id,
        stage_name="inventory",
        status=StageStatus.PENDING,
        order=1,
        created_at=now,
        updated_at=now,
    )
    stage_repo.save(stage)

    # Worker 1 updates stage
    w1_stage = stage_repo.get_by_id(stage.id)
    assert w1_stage is not None
    w1_updated = w1_stage.transition_to(
        StageStatus.RUNNING,
        updated_at=datetime.now(UTC),
        processed_items=5,
    )
    stage_repo.update(w1_updated, expected_version=1)

    # Worker 2 tries with stale version
    w2_stage = stage
    w2_updated = w2_stage.transition_to(
        StageStatus.RUNNING,
        updated_at=datetime.now(UTC),
        processed_items=10,
    )
    with pytest.raises(AnalysisStateConflictError):
        stage_repo.update(w2_updated, expected_version=1)
