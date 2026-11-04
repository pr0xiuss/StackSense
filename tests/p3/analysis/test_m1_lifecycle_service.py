"""Tests for AnalysisLifecycleService operations and lifecycle rules."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.platform.analysis.application.dto import CreateAnalysisRequest
from backend.platform.analysis.application.lifecycle_service import (
    AnalysisLifecycleService,
)
from backend.platform.analysis.domain.constants import AnalysisStatus, JobStatus
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
from backend.platform.errors import (
    AnalysisCancellationNotAllowedError,
    AnalysisInputError,
    AnalysisIntegrityError,
    AnalysisNotFoundError,
    AnalysisStateConflictError,
    RepositoryNotFoundError,
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
def service(session: Session) -> AnalysisLifecycleService:
    """Build a fully wired AnalysisLifecycleService backed by SQLite."""
    return AnalysisLifecycleService(
        analysis_repo=SqlAlchemyAnalysisRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        stage_repo=SqlAlchemyStageRepository(session),
        event_repo=SqlAlchemyEventRepository(session),
        diagnostic_repo=SqlAlchemyDiagnosticRepository(session),
        revision_repo=SqlAlchemyRevisionRepository(session),
        project_repo=SqlAlchemyProjectRepository(session),
        repository_repo=SqlAlchemyRepositoryRepository(session),
    )


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


# --- Create Analysis Tests ---


def test_create_analysis_success(
    service: AnalysisLifecycleService, session: Session
) -> None:
    project, repo, rev = _setup_fixtures(session)

    req = CreateAnalysisRequest(
        project_id=project.id,
        repository_id=repo.id,
        revision_id=rev.id,
        include_paths=("src/",),
        timeout_seconds=900,
    )

    resp = service.create_analysis(req)
    assert resp.project_id == project.id
    assert resp.repository_id == repo.id
    assert resp.snapshot_id == rev.id
    assert resp.status == AnalysisStatus.CREATED.value
    assert len(resp.stages) == 9
    assert resp.active_job is not None
    assert resp.active_job.status == JobStatus.PENDING.value


def test_create_analysis_idempotency_replay(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(session)

    req = CreateAnalysisRequest(
        project_id=project.id,
        repository_id=repo.id,
        revision_id=rev.id,
        idempotency_key="idemp-key-1",
    )

    first = service.create_analysis(req)
    second = service.create_analysis(req)

    assert first.id == second.id
    assert first.created_at == second.created_at


def test_create_analysis_invalid_project(
    service: AnalysisLifecycleService, session: Session
) -> None:
    _, repo, rev = _setup_fixtures(session)

    req = CreateAnalysisRequest(
        project_id=uuid4(),  # Non-existent
        repository_id=repo.id,
        revision_id=rev.id,
    )

    with pytest.raises(AnalysisInputError):
        service.create_analysis(req)


def test_create_analysis_invalid_repository(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, _, rev = _setup_fixtures(session)

    req = CreateAnalysisRequest(
        project_id=project.id,
        repository_id=uuid4(),  # Non-existent
        revision_id=rev.id,
    )

    with pytest.raises(RepositoryNotFoundError):
        service.create_analysis(req)


def test_create_analysis_revision_ownership_mismatch(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, repo, _ = _setup_fixtures(session)

    # Revision belonging to another project
    other_rev = RevisionModel(
        id=uuid4(),
        project_id=uuid4(),
        repository_id=repo.id,
        revision_identifier="commit-200",
        source_hash="sha-200",
        total_files=0,
        total_bytes=0,
        created_at=datetime.now(UTC),
    )
    session.add(other_rev)
    session.flush()

    req = CreateAnalysisRequest(
        project_id=project.id,
        repository_id=repo.id,
        revision_id=other_rev.id,
    )

    with pytest.raises(AnalysisIntegrityError):
        service.create_analysis(req)


# --- Get & List Analyses Tests ---


def test_get_analysis_success_and_not_found(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(session)

    req = CreateAnalysisRequest(
        project_id=project.id,
        repository_id=repo.id,
        revision_id=rev.id,
    )
    created = service.create_analysis(req)

    fetched = service.get_analysis(created.id, project.id)
    assert fetched.id == created.id
    assert len(fetched.stages) == 9

    with pytest.raises(AnalysisNotFoundError):
        service.get_analysis(uuid4(), project.id)


def test_list_analyses_pagination(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(session)

    for i in range(3):
        service.create_analysis(
            CreateAnalysisRequest(
                project_id=project.id,
                repository_id=repo.id,
                revision_id=rev.id,
                idempotency_key=f"key-{i}",
            )
        )

    listing = service.list_analyses(project.id, limit=2, offset=0)
    assert len(listing.items) == 2
    assert listing.total == 3


# --- Cancellation Tests ---


def test_cancel_analysis_while_queued(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)

    created = service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )

    # Advance to QUEUED to test queued cancellation
    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    queued = analysis.transition_to(AnalysisStatus.QUEUED, updated_at=datetime.now(UTC))
    analysis_repo.update(queued, expected_version=analysis.version)

    cancelled = service.cancel_analysis(
        created.id, project.id, reason="User requested cancel"
    )
    assert cancelled.status == AnalysisStatus.CANCELLED.value
    assert cancelled.active_job is not None
    assert cancelled.active_job.status == JobStatus.CANCELLED.value


def test_cancel_analysis_while_created_transitions_to_failed(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(session)

    created = service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )

    cancelled = service.cancel_analysis(
        created.id, project.id, reason="User requested cancel"
    )
    assert cancelled.status == AnalysisStatus.FAILED.value
    assert cancelled.error_code == "analysis_cancelled"
    assert cancelled.active_job is not None
    assert cancelled.active_job.status == JobStatus.CANCELLED.value


def test_cancel_terminal_analysis_raises_error(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(session)

    created = service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    service.cancel_analysis(created.id, project.id)

    # Second cancel on terminal state
    with pytest.raises(AnalysisCancellationNotAllowedError):
        service.cancel_analysis(created.id, project.id)


# --- Timeout Tests ---


def test_record_timeout_transitions_to_failed(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)

    created = service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )

    # Manually advance to RUNNING to test timeout
    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    queued = analysis.transition_to(AnalysisStatus.QUEUED, updated_at=datetime.now(UTC))
    running = queued.transition_to(AnalysisStatus.RUNNING, updated_at=datetime.now(UTC))
    analysis_repo.update(running, expected_version=1)

    # Record timeout
    timed_out = service.record_timeout(created.id, project.id)
    assert timed_out.status == AnalysisStatus.FAILED.value
    assert timed_out.error_code == "analysis_timeout"
    assert timed_out.active_job is not None
    assert timed_out.active_job.status == JobStatus.FAILED.value


def test_record_timeout_on_non_running_raises_conflict(
    service: AnalysisLifecycleService,
    session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(session)

    created = service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )

    with pytest.raises(AnalysisStateConflictError):
        service.record_timeout(created.id, project.id)
