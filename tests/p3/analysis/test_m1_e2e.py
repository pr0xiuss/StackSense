"""End-to-End integration test for Module 1 execution pipeline with fake handlers."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.app import app
from backend.platform.analysis.application.dependencies import (
    get_analysis_orchestrator,
    get_platform_repository_gateway,
    get_queue_publisher,
)
from backend.platform.analysis.application.input_factory import (
    PlatformAnalysisInputFactory,
)
from backend.platform.analysis.application.registry import create_fake_handler_registry
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


def _delegated_headers(project_id: object) -> dict[str, str]:
    return {
        "X-Service-Token": SERVICE_SECRET,
        "X-Actor-Id": str(uuid4()),
        "X-Actor-Role": "ADMIN",
        "X-Project-Id": str(project_id),
    }


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


def test_m1_end_to_end_lifecycle_pipeline(
    client: TestClient,
    db_session: Session,
    queue_publisher: InMemoryAnalysisQueuePublisher,
) -> None:
    """Validate flow: POST create -> queue -> worker -> SSE replay."""
    project, repo, rev = _setup_fixtures(db_session)
    idempotency_key = f"e2e-idem-{uuid4()}"

    # 1. API: Initiate Analysis
    create_res = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
            "idempotency_key": idempotency_key,
        },
    )
    assert create_res.status_code == 202
    created_data = create_res.json()
    analysis_id = UUID(created_data["id"])
    assert created_data["status"] == "queued"
    assert created_data["active_job"]["status"] == "queued"
    job_id = UUID(created_data["active_job"]["id"])

    # 2. Queue verification: Message dispatched to queue with identifier-only payload
    assert len(queue_publisher.published_jobs) == 1
    queue_msg = queue_publisher.published_jobs[0]
    assert queue_msg.analysis_id == analysis_id
    assert queue_msg.job_id == job_id
    assert queue_msg.project_id == project.id

    # 3. Worker Execution: Run orchestrator simulating background worker processing
    orchestrator = get_analysis_orchestrator(
        session=db_session,
        settings=get_settings(),
        registry=create_fake_handler_registry(),
        input_factory=PlatformAnalysisInputFactory(
            SqlAlchemyTestPlatformGateway(db_session)
        ),
    )
    orchestrator.execute(
        analysis_id=analysis_id,
        job_id=job_id,
        project_id=project.id,
        worker_id="worker-e2e-1",
    )

    # 4. REST Verification: Check analysis has completed and all 9 stages passed
    get_res = client.get(
        f"/api/v1/analyses/{analysis_id}?project_id={project.id}",
        headers=_delegated_headers(project.id),
    )
    assert get_res.status_code == 200
    final_data = get_res.json()
    assert final_data["status"] == "completed"
    assert len(final_data["stages"]) == 9
    for stg in final_data["stages"]:
        assert stg["status"] == "completed"

    # 5. SSE Verification: Stream durable events from start to finish
    sse_res = client.get(
        f"/api/v1/analyses/{analysis_id}/events?project_id={project.id}",
        headers=_delegated_headers(project.id),
    )
    assert sse_res.status_code == 200
    stream_content = sse_res.text
    assert "event: analysis.created" in stream_content
    assert "event: analysis.queued" in stream_content
    assert "event: analysis.started" in stream_content
    assert "event: analysis.stage.started" in stream_content
    assert "event: analysis.stage.completed" in stream_content
    assert "event: analysis.completed" in stream_content

    # 6. Idempotency Verification: Replay POST returns completed state
    # without duplicate job
    replay_res = client.post(
        "/api/v1/analyses",
        headers=_delegated_headers(project.id),
        json={
            "project_id": str(project.id),
            "repository_id": str(repo.id),
            "revision_id": str(rev.id),
            "idempotency_key": idempotency_key,
        },
    )
    assert replay_res.status_code == 202
    assert replay_res.json()["id"] == str(analysis_id)
    assert replay_res.json()["status"] == "completed"
    # No duplicate message published to queue
    assert len(queue_publisher.published_jobs) == 1
