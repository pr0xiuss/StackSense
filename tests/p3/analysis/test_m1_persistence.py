"""Persistence integration tests for M1 SQLAlchemy repositories."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.platform.analysis.domain.analysis import (
    Analysis,
    AnalysisCompleteness,
    AnalysisConfiguration,
)
from backend.platform.analysis.domain.constants import (
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


# --- Analysis Repository Tests ---


def test_analysis_repository_save_and_get(session: Session) -> None:
    project, repo, rev = _setup_entities(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)

    now = datetime.now(UTC)
    analysis = Analysis(
        id=uuid4(),
        project_id=project.id,
        repository_id=repo.id,
        snapshot_id=rev.id,
        status=AnalysisStatus.CREATED,
        configuration=AnalysisConfiguration(include_paths=("src/",)),
        completeness=AnalysisCompleteness(analyzed_files_count=10),
        created_at=now,
        updated_at=now,
    )

    saved = analysis_repo.save(analysis, idempotency_key="key-123")
    assert saved.id == analysis.id

    fetched = analysis_repo.get_by_id(analysis.id, project.id)
    assert fetched is not None
    assert fetched.id == analysis.id
    assert fetched.status == AnalysisStatus.CREATED
    assert fetched.configuration.include_paths == ("src/",)
    assert fetched.completeness is not None
    assert fetched.completeness.analyzed_files_count == 10

    # Idempotency lookup
    by_key = analysis_repo.get_by_idempotency_key(project.id, "key-123")
    assert by_key is not None
    assert by_key.id == analysis.id


def test_analysis_repository_optimistic_update(session: Session) -> None:
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

    # Valid update
    updated = analysis.transition_to(
        AnalysisStatus.QUEUED,
        updated_at=datetime.now(UTC),
    )
    analysis_repo.update(updated, expected_version=1)

    fetched = analysis_repo.get_by_id(analysis.id, project.id)
    assert fetched is not None
    assert fetched.status == AnalysisStatus.QUEUED
    assert fetched.version == 2

    # Conflict on stale version
    stale_update = updated.transition_to(
        AnalysisStatus.RUNNING,
        updated_at=datetime.now(UTC),
    )
    with pytest.raises(AnalysisStateConflictError):
        analysis_repo.update(
            stale_update, expected_version=1
        )  # expected 1 while current is 2


def test_analysis_repository_project_isolation_and_listing(session: Session) -> None:
    project1, repo1, rev1 = _setup_entities(session)
    project2, repo2, rev2 = _setup_entities(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)

    now = datetime.now(UTC)
    a1 = Analysis(
        id=uuid4(),
        project_id=project1.id,
        repository_id=repo1.id,
        snapshot_id=rev1.id,
        status=AnalysisStatus.CREATED,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )
    a2 = Analysis(
        id=uuid4(),
        project_id=project2.id,
        repository_id=repo2.id,
        snapshot_id=rev2.id,
        status=AnalysisStatus.COMPLETED,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )
    analysis_repo.save(a1)
    analysis_repo.save(a2)

    # Cross-project get isolation
    assert analysis_repo.get_by_id(a1.id, project2.id) is None

    # Listing isolation
    p1_items = analysis_repo.list_by_project(project1.id, limit=10, offset=0)
    assert len(p1_items) == 1
    assert p1_items[0].id == a1.id

    assert analysis_repo.count_by_project(project1.id) == 1
    assert analysis_repo.count_by_project(project2.id) == 1


# --- Job Repository Tests ---


def test_job_repository_save_get_update(session: Session) -> None:
    project, repo, rev = _setup_entities(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    job_repo = SqlAlchemyJobRepository(session)

    now = datetime.now(UTC)
    analysis_id = uuid4()
    analysis = Analysis(
        id=analysis_id,
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
        analysis_id=analysis_id,
        project_id=project.id,
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    job_repo.save(job)

    fetched = job_repo.get_by_id(job.id)
    assert fetched is not None
    assert fetched.status == JobStatus.PENDING

    active = job_repo.get_active_for_analysis(analysis_id)
    assert active is not None
    assert active.id == job.id

    # Update job to running
    updated_job = job.transition_to(
        JobStatus.RUNNING,
        updated_at=datetime.now(UTC),
        worker_id="worker-1",
        heartbeat_at=datetime.now(UTC),
    )
    job_repo.update(updated_job, expected_version=1)

    fetched_updated = job_repo.get_by_id(job.id)
    assert fetched_updated is not None
    assert fetched_updated.status == JobStatus.RUNNING
    assert fetched_updated.worker_id == "worker-1"

    # Stale job detection
    old_time = datetime.now(UTC) + timedelta(minutes=5)
    stale_jobs = job_repo.find_stale_jobs(heartbeat_cutoff=old_time)
    assert len(stale_jobs) == 1


# --- Stage Repository Tests ---


def test_stage_repository_batch_and_ordering(session: Session) -> None:
    project, repo, rev = _setup_entities(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    stage_repo = SqlAlchemyStageRepository(session)

    now = datetime.now(UTC)
    analysis_id = uuid4()
    analysis = Analysis(
        id=analysis_id,
        project_id=project.id,
        repository_id=repo.id,
        snapshot_id=rev.id,
        status=AnalysisStatus.CREATED,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )
    analysis_repo.save(analysis)

    stages = [
        AnalysisStage(
            id=uuid4(),
            analysis_id=analysis_id,
            stage_name="inventory",
            status=StageStatus.PENDING,
            order=2,
            created_at=now,
            updated_at=now,
        ),
        AnalysisStage(
            id=uuid4(),
            analysis_id=analysis_id,
            stage_name="input_validation",
            status=StageStatus.PENDING,
            order=1,
            created_at=now,
            updated_at=now,
        ),
    ]
    stage_repo.save_batch(stages)

    # list_by_analysis should return ordered by stage_order (order 1 then order 2)
    ordered = stage_repo.list_by_analysis(analysis_id)
    assert len(ordered) == 2
    assert ordered[0].stage_name == "input_validation"
    assert ordered[1].stage_name == "inventory"

    by_name = stage_repo.get_by_name(analysis_id, "inventory")
    assert by_name is not None
    assert by_name.stage_name == "inventory"


# --- Event Repository Tests ---


def test_event_repository_sequence_and_listing(session: Session) -> None:
    project, repo, rev = _setup_entities(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    event_repo = SqlAlchemyEventRepository(session)

    now = datetime.now(UTC)
    analysis_id = uuid4()
    analysis = Analysis(
        id=analysis_id,
        project_id=project.id,
        repository_id=repo.id,
        snapshot_id=rev.id,
        status=AnalysisStatus.CREATED,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )
    analysis_repo.save(analysis)

    assert event_repo.get_latest_sequence_number(analysis_id) == 0

    e1 = AnalysisEvent(
        id=uuid4(),
        analysis_id=analysis_id,
        sequence_number=1,
        event_type=AnalysisEventType.ANALYSIS_CREATED,
        timestamp=now,
        payload={"step": 1},
    )
    e2 = AnalysisEvent(
        id=uuid4(),
        analysis_id=analysis_id,
        sequence_number=2,
        event_type=AnalysisEventType.ANALYSIS_QUEUED,
        timestamp=now,
        payload={"step": 2},
    )
    event_repo.append(e1)
    event_repo.append(e2)

    assert event_repo.get_latest_sequence_number(analysis_id) == 2

    all_events = event_repo.list_by_analysis(analysis_id, after_sequence=0)
    assert len(all_events) == 2
    assert all_events[0].sequence_number == 1
    assert all_events[1].sequence_number == 2

    # after_sequence replay filter
    after_one = event_repo.list_by_analysis(analysis_id, after_sequence=1)
    assert len(after_one) == 1
    assert after_one[0].sequence_number == 2


# --- Diagnostic Repository Tests ---


def test_diagnostic_repository_save_and_filtering(session: Session) -> None:
    project, repo, rev = _setup_entities(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    diag_repo = SqlAlchemyDiagnosticRepository(session)

    now = datetime.now(UTC)
    analysis_id = uuid4()
    analysis = Analysis(
        id=analysis_id,
        project_id=project.id,
        repository_id=repo.id,
        snapshot_id=rev.id,
        status=AnalysisStatus.CREATED,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )
    analysis_repo.save(analysis)

    d1 = AnalysisDiagnostic(
        id=uuid4(),
        analysis_id=analysis_id,
        code="warn_code",
        category=DiagnosticCategory.PARSING,
        severity=DiagnosticSeverity.WARNING,
        scope=DiagnosticScope.FILE,
        message="Warning message",
        retryability=FailureRetryability.NON_RETRYABLE,
        stage="syntax_extraction",
        created_at=now,
    )
    d2 = AnalysisDiagnostic(
        id=uuid4(),
        analysis_id=analysis_id,
        code="err_code",
        category=DiagnosticCategory.ANALYSIS,
        severity=DiagnosticSeverity.ERROR,
        scope=DiagnosticScope.ANALYSIS,
        message="Error message",
        retryability=FailureRetryability.NON_RETRYABLE,
        stage="architecture_build",
        created_at=now,
    )

    diag_repo.save_batch([d1, d2])

    assert diag_repo.count_by_analysis(analysis_id) == 2
    assert (
        diag_repo.count_by_analysis(analysis_id, severity=DiagnosticSeverity.ERROR) == 1
    )

    # Filter by stage
    syntax_diags = diag_repo.list_by_analysis(analysis_id, stage="syntax_extraction")
    assert len(syntax_diags) == 1
    assert syntax_diags[0].code == "warn_code"
