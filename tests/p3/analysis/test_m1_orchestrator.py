"""Tests for AnalysisOrchestrator pipeline execution, cancellation, and timeout."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.platform.analysis.application.dto import CreateAnalysisRequest
from backend.platform.analysis.application.execution import (
    ExecutionContext,
)
from backend.platform.analysis.application.input_factory import AnalysisInputFactory
from backend.platform.analysis.application.lifecycle_service import (
    AnalysisLifecycleService,
)
from backend.platform.analysis.application.orchestrator import (
    AnalysisOrchestrator,
)
from backend.platform.analysis.application.registry import (
    FakeStageHandler,
    StageHandlerRegistry,
    create_fake_handler_registry,
)
from backend.platform.analysis.domain.constants import (
    AnalysisStageName,
    AnalysisStatus,
    JobStatus,
    StageStatus,
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
from backend.platform.ingestion.infra.artifact_repository import (
    SqlAlchemyArtifactRepository,
)
from backend.platform.ingestion.infra.model import (
    ArtifactModel,
    IngestionModel,
    RevisionModel,
)
from backend.platform.ingestion.infra.revision_repository import (
    SqlAlchemyRevisionRepository,
)
from backend.platform.ingestion.infra.storage.local_storage import (
    LocalStorageService,
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
def session(tmp_path: object) -> Generator[Session]:
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


def _build_orchestrator(
    session: Session,
    tmp_path: str,
    *,
    registry: StageHandlerRegistry | None = None,
    max_duration_seconds: int = 1800,
) -> tuple[AnalysisOrchestrator, AnalysisLifecycleService]:
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    job_repo = SqlAlchemyJobRepository(session)
    stage_repo = SqlAlchemyStageRepository(session)
    event_repo = SqlAlchemyEventRepository(session)
    diagnostic_repo = SqlAlchemyDiagnosticRepository(session)
    revision_repo = SqlAlchemyRevisionRepository(session)
    artifact_repo = SqlAlchemyArtifactRepository(session)
    project_repo = SqlAlchemyProjectRepository(session)
    repository_repo = SqlAlchemyRepositoryRepository(session)
    storage_service = LocalStorageService(str(tmp_path))

    input_factory = AnalysisInputFactory(
        revision_repo=revision_repo,
        artifact_repo=artifact_repo,
        storage_service=storage_service,
        repository_repo=repository_repo,
    )

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

    orchestrator = AnalysisOrchestrator(
        analysis_repo=analysis_repo,
        job_repo=job_repo,
        stage_repo=stage_repo,
        event_repo=event_repo,
        diagnostic_repo=diagnostic_repo,
        input_factory=input_factory,
        registry=registry or create_fake_handler_registry(),
        max_duration_seconds=max_duration_seconds,
    )

    return orchestrator, lifecycle_service


def test_orchestrator_successful_execution_all_stages(
    session: Session, tmp_path: str
) -> None:
    project, repo, rev = _setup_fixtures(session)
    orchestrator, lifecycle_service = _build_orchestrator(session, tmp_path)

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    # Execute
    orchestrator.execute(
        analysis_id=created.id,
        job_id=created.active_job.id,
        project_id=project.id,
        worker_id="worker-test-1",
    )

    # Verify Analysis is COMPLETED
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    assert analysis.status == AnalysisStatus.COMPLETED
    assert analysis.completed_at is not None

    # Verify Job is COMPLETED
    job_repo = SqlAlchemyJobRepository(session)
    job = job_repo.get_by_id(created.active_job.id)
    assert job is not None
    assert job.status == JobStatus.COMPLETED
    assert job.completed_at is not None
    assert job.worker_id == "worker-test-1"

    # Verify all 9 stages are COMPLETED
    stage_repo = SqlAlchemyStageRepository(session)
    stages = stage_repo.list_by_analysis(created.id)
    assert len(stages) == 9
    for s in stages:
        assert s.status == StageStatus.COMPLETED
        assert s.completed_at is not None

    # Verify event sequence
    event_repo = SqlAlchemyEventRepository(session)
    events = event_repo.list_by_analysis(created.id)
    event_types = [e.event_type.value for e in events]
    assert "analysis.created" in event_types
    assert "analysis.queued" in event_types
    assert "analysis.started" in event_types
    assert "analysis.stage.started" in event_types
    assert "analysis.stage.completed" in event_types
    assert "analysis.completed" in event_types


def test_orchestrator_mandatory_stage_failure_marks_analysis_failed(
    session: Session, tmp_path: str
) -> None:
    project, repo, rev = _setup_fixtures(session)

    # Configure syntax_extraction to fail
    registry = create_fake_handler_registry(
        override_status={
            AnalysisStageName.SYNTAX_EXTRACTION.value: StageStatus.FAILED,
        }
    )
    orchestrator, lifecycle_service = _build_orchestrator(
        session, tmp_path, registry=registry
    )

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    orchestrator.execute(
        analysis_id=created.id,
        job_id=created.active_job.id,
        project_id=project.id,
    )

    analysis_repo = SqlAlchemyAnalysisRepository(session)
    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    assert analysis.status == AnalysisStatus.FAILED

    job_repo = SqlAlchemyJobRepository(session)
    job = job_repo.get_by_id(created.active_job.id)
    assert job is not None
    assert job.status == JobStatus.FAILED

    # Check stage statuses
    stage_repo = SqlAlchemyStageRepository(session)
    stages = stage_repo.list_by_analysis(created.id)
    stage_dict = {s.stage_name: s.status for s in stages}
    assert stage_dict[AnalysisStageName.INPUT_VALIDATION.value] == StageStatus.COMPLETED
    assert stage_dict[AnalysisStageName.SYNTAX_EXTRACTION.value] == StageStatus.FAILED
    assert stage_dict[AnalysisStageName.IR_CONSTRUCTION.value] == StageStatus.PENDING


def test_orchestrator_missing_mandatory_handler_raises_configuration_error(
    session: Session, tmp_path: str
) -> None:
    project, repo, rev = _setup_fixtures(session)

    # Empty registry with no handlers
    empty_registry = StageHandlerRegistry()
    orchestrator, lifecycle_service = _build_orchestrator(
        session, tmp_path, registry=empty_registry
    )

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    orchestrator.execute(
        analysis_id=created.id,
        job_id=created.active_job.id,
        project_id=project.id,
    )

    analysis_repo = SqlAlchemyAnalysisRepository(session)
    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    assert analysis.status == AnalysisStatus.FAILED
    assert analysis.error_code == "execution_error"


def test_orchestrator_cooperative_cancellation_checkpoint(
    session: Session, tmp_path: str
) -> None:
    project, repo, rev = _setup_fixtures(session)
    analysis_repo = SqlAlchemyAnalysisRepository(session)

    # Custom hook that requests cancellation during language detection
    def cancel_hook(ctx: ExecutionContext) -> None:
        a = analysis_repo.get_by_id(ctx.analysis_id, ctx.project_id)
        assert a is not None
        req = a.transition_to(
            AnalysisStatus.CANCEL_REQUESTED, updated_at=datetime.now(UTC)
        )
        analysis_repo.update(req, expected_version=a.version)
        ctx.check_cancellation()

    hook_handler = FakeStageHandler(
        stage_name=AnalysisStageName.LANGUAGE_DETECTION.value,
        custom_execute_hook=cancel_hook,
    )
    registry = create_fake_handler_registry(
        override_handlers={
            AnalysisStageName.LANGUAGE_DETECTION.value: hook_handler,
        }
    )
    orchestrator, lifecycle_service = _build_orchestrator(
        session, tmp_path, registry=registry
    )

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    orchestrator.execute(
        analysis_id=created.id,
        job_id=created.active_job.id,
        project_id=project.id,
    )

    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    assert analysis.status == AnalysisStatus.CANCELLED

    job_repo = SqlAlchemyJobRepository(session)
    job = job_repo.get_by_id(created.active_job.id)
    assert job is not None
    assert job.status == JobStatus.CANCELLED


def test_orchestrator_timeout_triggers_failed(session: Session, tmp_path: str) -> None:
    project, repo, rev = _setup_fixtures(session)
    # 0 second max duration -> immediate timeout
    orchestrator, lifecycle_service = _build_orchestrator(
        session, tmp_path, max_duration_seconds=-1
    )

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    orchestrator.execute(
        analysis_id=created.id,
        job_id=created.active_job.id,
        project_id=project.id,
    )

    analysis_repo = SqlAlchemyAnalysisRepository(session)
    analysis = analysis_repo.get_by_id(created.id, project.id)
    assert analysis is not None
    assert analysis.status == AnalysisStatus.FAILED
    assert analysis.error_code == "analysis_timeout"


def test_orchestrator_duplicate_terminal_job_call_is_idempotent(
    session: Session, tmp_path: str
) -> None:
    project, repo, rev = _setup_fixtures(session)
    orchestrator, lifecycle_service = _build_orchestrator(session, tmp_path)

    created = lifecycle_service.create_analysis(
        CreateAnalysisRequest(
            project_id=project.id,
            repository_id=repo.id,
            revision_id=rev.id,
        )
    )
    assert created.active_job is not None

    # First execution -> completes
    orchestrator.execute(
        analysis_id=created.id,
        job_id=created.active_job.id,
        project_id=project.id,
    )

    analysis_repo = SqlAlchemyAnalysisRepository(session)
    first_analysis = analysis_repo.get_by_id(created.id, project.id)
    assert first_analysis is not None
    assert first_analysis.status == AnalysisStatus.COMPLETED
    first_version = first_analysis.version

    # Duplicate delivery -> no-op
    orchestrator.execute(
        analysis_id=created.id,
        job_id=created.active_job.id,
        project_id=project.id,
    )

    second_analysis = analysis_repo.get_by_id(created.id, project.id)
    assert second_analysis is not None
    assert second_analysis.version == first_version
