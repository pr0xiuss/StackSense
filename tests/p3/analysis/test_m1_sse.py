"""Tests for Server-Sent Events (SSE) durable streaming and sequence replay."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.app import app
from backend.platform.analysis.application.dto import CreateAnalysisRequest
from backend.platform.analysis.application.events import LifecycleEventEmitter
from backend.platform.analysis.application.lifecycle_service import (
    AnalysisLifecycleService,
)
from backend.platform.analysis.domain.constants import AnalysisStatus
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
from backend.platform.config import get_settings
from backend.platform.dependency_injection import get_database_session
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

SERVICE_SECRET = get_settings().internal_api_secret_key.get_secret_value()


@pytest.fixture
def db_session() -> Generator[Session]:
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
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    sess = session_factory()
    try:
        yield sess
        sess.commit()
    finally:
        sess.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient]:
    def override_session() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_database_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


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


def _build_lifecycle_service(session: Session) -> AnalysisLifecycleService:
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


def test_sse_streaming_events_delivered_in_order(
    client: TestClient, db_session: Session
) -> None:
    project, repo, rev = _setup_fixtures(db_session)
    service = _build_lifecycle_service(db_session)

    created = service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )

    # Append additional events
    event_repo = SqlAlchemyEventRepository(db_session)
    emitter = LifecycleEventEmitter(event_repo, created.id)
    emitter.emit_started(created.active_job.id if created.active_job else uuid4())
    emitter.emit_completed()

    # Advance analysis through valid lifecycle states to COMPLETED
    analysis_repo = SqlAlchemyAnalysisRepository(db_session)
    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    now = datetime.now(UTC)
    queued = analysis.transition_to(AnalysisStatus.QUEUED, updated_at=now)
    running = queued.transition_to(
        AnalysisStatus.RUNNING, updated_at=now, started_at=now
    )
    completed = running.transition_to(
        AnalysisStatus.COMPLETED, updated_at=now, completed_at=now
    )
    analysis_repo.update(completed, expected_version=analysis.version)

    # Stream events
    res = client.get(
        f"/api/v1/analyses/{created.id}/events?project_id={project.id}",
        headers={"X-Service-Token": SERVICE_SECRET},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    body = res.text
    assert "id: 1" in body
    assert "event: analysis.created" in body
    assert "id: 2" in body
    assert "event: analysis.started" in body
    assert "id: 3" in body
    assert "event: analysis.completed" in body


def test_sse_replay_from_after_sequence(
    client: TestClient, db_session: Session
) -> None:
    project, repo, rev = _setup_fixtures(db_session)
    service = _build_lifecycle_service(db_session)

    created = service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )

    event_repo = SqlAlchemyEventRepository(db_session)
    emitter = LifecycleEventEmitter(event_repo, created.id)
    emitter.emit_started(created.active_job.id if created.active_job else uuid4())
    emitter.emit_completed()

    analysis_repo = SqlAlchemyAnalysisRepository(db_session)
    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    now = datetime.now(UTC)
    queued = analysis.transition_to(AnalysisStatus.QUEUED, updated_at=now)
    running = queued.transition_to(
        AnalysisStatus.RUNNING, updated_at=now, started_at=now
    )
    completed = running.transition_to(
        AnalysisStatus.COMPLETED, updated_at=now, completed_at=now
    )
    analysis_repo.update(completed, expected_version=analysis.version)

    # Replay after sequence 2 -> should only get sequence 3
    res = client.get(
        f"/api/v1/analyses/{created.id}/events?project_id={project.id}&after_sequence=2",
        headers={"X-Service-Token": SERVICE_SECRET},
    )
    assert res.status_code == 200
    body = res.text
    assert "id: 1" not in body
    assert "id: 2" not in body
    assert "id: 3" in body
    assert "event: analysis.completed" in body


def test_sse_replay_with_last_event_id_header(
    client: TestClient, db_session: Session
) -> None:
    project, repo, rev = _setup_fixtures(db_session)
    service = _build_lifecycle_service(db_session)

    created = service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )

    event_repo = SqlAlchemyEventRepository(db_session)
    emitter = LifecycleEventEmitter(event_repo, created.id)
    emitter.emit_started(created.active_job.id if created.active_job else uuid4())
    emitter.emit_completed()

    analysis_repo = SqlAlchemyAnalysisRepository(db_session)
    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    now = datetime.now(UTC)
    queued = analysis.transition_to(AnalysisStatus.QUEUED, updated_at=now)
    running = queued.transition_to(
        AnalysisStatus.RUNNING, updated_at=now, started_at=now
    )
    completed = running.transition_to(
        AnalysisStatus.COMPLETED, updated_at=now, completed_at=now
    )
    analysis_repo.update(completed, expected_version=analysis.version)

    # Header Last-Event-ID: 1 -> receives sequences > 1 (2 and 3)
    res = client.get(
        f"/api/v1/analyses/{created.id}/events?project_id={project.id}",
        headers={
            "X-Service-Token": SERVICE_SECRET,
            "Last-Event-ID": "1",
        },
    )
    assert res.status_code == 200
    body = res.text
    assert "id: 1\n" not in body
    assert "id: 2" in body
    assert "id: 3" in body


def test_sse_nonexistent_analysis_returns_404(
    client: TestClient, db_session: Session
) -> None:
    project, repo, rev = _setup_fixtures(db_session)
    non_existent = uuid4()

    res = client.get(
        f"/api/v1/analyses/{non_existent}/events?project_id={project.id}",
        headers={"X-Service-Token": SERVICE_SECRET},
    )
    assert res.status_code == 404
