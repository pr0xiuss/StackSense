"""Tests for internal lifecycle REST API endpoints."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.app import app
from backend.platform.analysis.application.dependencies import (
    get_platform_repository_gateway,
    get_queue_publisher,
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
from backend.platform.config import get_settings
from backend.platform.dependency_injection import get_database_session
from backend.platform.ingestion.infra.model import (
    ArtifactModel,
    IngestionModel,
    RevisionModel,
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
from tests.p3.analysis.platform_gateway_stub import SqlAlchemyTestPlatformGateway

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
        engine.dispose()


@pytest.fixture
def queue_publisher() -> InMemoryAnalysisQueuePublisher:
    return InMemoryAnalysisQueuePublisher()


@pytest.fixture
def client(
    db_session: Session, queue_publisher: InMemoryAnalysisQueuePublisher
) -> Generator[TestClient]:
    def override_session() -> Generator[Session]:
        yield db_session

    def override_queue() -> InMemoryAnalysisQueuePublisher:
        return queue_publisher

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_queue_publisher] = override_queue
    app.dependency_overrides[get_platform_repository_gateway] = (
        lambda: SqlAlchemyTestPlatformGateway(db_session)
    )
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


def _delegated_headers(project_id: object, role: str = "ADMIN") -> dict[str, str]:
    return {
        "X-Service-Token": SERVICE_SECRET,
        "X-Actor-Id": str(uuid4()),
        "X-Actor-Role": role,
        "X-Project-Id": str(project_id),
    }


def test_api_create_analysis_success_returns_202(
    client: TestClient,
    db_session: Session,
    queue_publisher: InMemoryAnalysisQueuePublisher,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)

    res = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
        },
    )

    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "queued"
    assert data["project_id"] == str(project.id)
    assert data["repository_id"] == str(repo.id)
    assert data["snapshot_id"] == str(rev.id)
    assert data["active_job"] is not None
    assert data["active_job"]["status"] == "queued"
    assert len(data["stages"]) == 9

    # Queue received job payload
    assert len(queue_publisher.published_jobs) == 1
    assert str(queue_publisher.published_jobs[0].analysis_id) == data["id"]


def test_api_create_analysis_with_operator_role_allowed(
    client: TestClient,
    db_session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)

    res = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id, "DEVELOPER"),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
        },
    )
    assert res.status_code == 202


def test_api_create_analysis_with_viewer_role_forbidden(
    client: TestClient,
    db_session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)

    res = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id, "VIEWER"),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
        },
    )
    assert res.status_code == 403


def test_api_create_analysis_missing_auth_returns_401(
    client: TestClient,
    db_session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)

    res = client.post(
        "/api/v1/analyses",
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
        },
    )
    assert res.status_code == 401


def test_api_list_analyses_returns_paginated(
    client: TestClient,
    db_session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)

    # Create 2 analyses
    for _ in range(2):
        client.post(
            "/api/v1/analyses",
            headers=_delegated_headers(project.id),
            json={
                "project_id": str(project.id),
                "repository_id": str(repo.id),
                "revision_id": str(rev.id),
            },
        )

    res = client.get(
        f"/api/v1/analyses?project_id={project.id}&limit=10&offset=0",
        headers=_delegated_headers(project.id),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["limit"] == 10
    assert data["offset"] == 0


def test_api_get_analysis_by_id(
    client: TestClient,
    db_session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)

    create_res = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
        },
    )
    analysis_id = create_res.json()["id"]

    res = client.get(
        f"/api/v1/analyses/{analysis_id}?project_id={project.id}",
        headers=_delegated_headers(project.id),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == analysis_id
    assert data["status"] == "queued"
    assert len(data["stages"]) == 9


def test_api_get_analysis_not_found_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)
    non_existent = uuid4()

    res = client.get(
        f"/api/v1/analyses/{non_existent}?project_id={project.id}",
        headers=_delegated_headers(project.id),
    )
    assert res.status_code == 404


def test_api_cancel_analysis_success(
    client: TestClient,
    db_session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)

    create_res = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
        },
    )
    analysis_id = create_res.json()["id"]

    cancel_res = client.post(
        f"/api/v1/analyses/{analysis_id}/cancel?project_id={project.id}",
        headers=_delegated_headers(project.id),
        json={"reason": "User cancelled"},
    )
    assert cancel_res.status_code == 200
    data = cancel_res.json()
    assert data["status"] == "cancelled"
    assert data["active_job"] is not None
    assert data["active_job"]["status"] == "cancelled"


def test_api_cancel_analysis_viewer_forbidden(
    client: TestClient,
    db_session: Session,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)

    create_res = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
        },
    )
    analysis_id = create_res.json()["id"]

    cancel_res = client.post(
        f"/api/v1/analyses/{analysis_id}/cancel?project_id={project.id}",
        headers=_delegated_headers(project.id, "VIEWER"),
        json={"reason": "User cancelled"},
    )
    assert cancel_res.status_code == 403


def test_api_create_analysis_idempotency_replay(
    client: TestClient,
    db_session: Session,
    queue_publisher: InMemoryAnalysisQueuePublisher,
) -> None:
    project, repo, rev = _setup_fixtures(db_session)
    idempotency_key = f"idem-{uuid4()}"

    res1 = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
            "idempotency_key": idempotency_key,
        },
    )
    assert res1.status_code == 202
    first_id = res1.json()["id"]
    assert len(queue_publisher.published_jobs) == 1

    # Second call with same idempotency_key returns identical analysis
    # without duplicate publish
    res2 = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
            "idempotency_key": idempotency_key,
        },
    )
    assert res2.status_code == 202
    assert res2.json()["id"] == first_id
    assert len(queue_publisher.published_jobs) == 1
