"""Integration tests for IngestionService orchestrating acquisition and storage."""

import zipfile
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database
from backend.platform.errors import (
    ActiveIngestionExistsError,
    ProjectAccessDeniedError,
    RepositoryNotFoundError,
    SourceValidationError,
)
from backend.platform.identity.domain.user import User
from backend.platform.ingestion.application.classifier import (
    ArtifactClassifier,
)
from backend.platform.ingestion.application.dto import (
    TriggerIngestionRequest,
)
from backend.platform.ingestion.application.service import (
    DefaultIngestionService,
)
from backend.platform.ingestion.application.validator import SourceValidator
from backend.platform.ingestion.domain.constants import IngestionStatus
from backend.platform.ingestion.infra.acquisition.directory_handler import (
    LocalDirectoryAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.zip_handler import (
    ZipArchiveAcquisitionHandler,
)
from backend.platform.ingestion.infra.artifact_repository import (
    SqlAlchemyArtifactRepository,
)
from backend.platform.ingestion.infra.ingestion_repository import (
    SqlAlchemyIngestionRepository,
)
from backend.platform.ingestion.infra.revision_repository import (
    SqlAlchemyRevisionRepository,
)
from backend.platform.ingestion.infra.storage.local_storage import (
    LocalStorageService,
)
from backend.platform.projects.application.access_service import (
    ProjectAccessService,
)
from backend.platform.projects.application.authorization import (
    ProjectAuthorization,
)
from backend.platform.projects.domain.project import Project
from backend.platform.projects.domain.project_role import ProjectRole
from backend.platform.projects.infra.access_repo import (
    SqlAlchemyProjectAccessRepository,
)
from backend.platform.projects.infra.repository import (
    SqlAlchemyProjectRepository,
)
from backend.platform.repositories.domain.repository import Repository
from backend.platform.repositories.infra.repository import (
    SqlAlchemyRepositoryRepository,
)
from tests.conftest import ensure_test_user


@pytest.fixture
def db_session() -> Generator[Session]:
    """Provide a database session for service integration tests."""
    database = get_database()
    session_generator = database.session()
    session = next(session_generator)

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session_generator.close()


def _create_zip_file(zip_path: Path, files: dict[str, bytes]) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return zip_path


def _setup_service(
    session: Session,
    tmp_path: Path,
) -> tuple[
    DefaultIngestionService,
    Project,
    Repository,
    User,  # owner
    User,  # viewer
    User,  # foreign
]:
    project_repo = SqlAlchemyProjectRepository(session)
    access_repo = SqlAlchemyProjectAccessRepository(session)
    access_service = ProjectAccessService(access_repo)
    authorization = ProjectAuthorization(access_service)
    repo_storage = SqlAlchemyRepositoryRepository(session)

    ingestion_repo = SqlAlchemyIngestionRepository(session)
    revision_repo = SqlAlchemyRevisionRepository(session)
    artifact_repo = SqlAlchemyArtifactRepository(session)
    storage_service = LocalStorageService(tmp_path / "storage_root")

    acquisition_handlers = [
        ZipArchiveAcquisitionHandler(),
        LocalDirectoryAcquisitionHandler(),
    ]
    validator = SourceValidator()
    classifier = ArtifactClassifier()

    service = DefaultIngestionService(
        project_authorization=authorization,
        repository_repo=repo_storage,
        ingestion_repo=ingestion_repo,
        revision_repo=revision_repo,
        artifact_repo=artifact_repo,
        storage_service=storage_service,
        acquisition_handlers=acquisition_handlers,
        validator=validator,
        classifier=classifier,
    )

    now = datetime.now(UTC)
    project = project_repo.save(
        Project(
            id=uuid4(),
            name=f"Ingest-Project-{uuid4().hex[:6]}",
            description="Project for ingestion testing",
            created_at=now,
            updated_at=now,
        )
    )

    repository = repo_storage.save(
        Repository(
            id=uuid4(),
            project_id=project.id,
            name=f"Ingest-Repo-{uuid4().hex[:6]}",
            description="Repository for ingestion testing",
            status="registered",
            created_at=now,
            updated_at=now,
        )
    )

    owner = ensure_test_user(uuid4())
    viewer = ensure_test_user(uuid4())
    foreign = ensure_test_user(uuid4())

    access_service.grant_access(project.id, owner.id, ProjectRole.OWNER)
    access_service.grant_access(project.id, viewer.id, ProjectRole.VIEWER)

    return service, project, repository, owner, viewer, foreign


def test_trigger_ingestion_success(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Test full successful ingestion pipeline from zip archive."""
    service, project, repository, owner, _, _ = _setup_service(db_session, tmp_path)

    zip_path = tmp_path / "sources" / "repo.zip"
    _create_zip_file(
        zip_path,
        {
            "src/main.py": b"def hello(): return 'world'\n",
            "package.json": b'{"name": "test"}\n',
            "README.md": b"# Test Repo Documentation\n",
        },
    )

    request = TriggerIngestionRequest(
        repository_id=repository.id,
        source_type="archive",
        source_reference=str(zip_path),
        revision_identifier="v1.0.0",
    )

    response = service.trigger_ingestion(request, user=owner)

    assert response.id is not None
    assert response.repository_id == repository.id
    assert response.project_id == project.id
    assert response.status == "completed"
    assert response.started_at is not None
    assert response.completed_at is not None
    assert response.error_code is None

    # Check revision created
    revisions = service.list_revisions(
        project.id, repository.id, user=owner, limit=10, offset=0
    )
    assert len(revisions) == 1
    rev = revisions[0]
    assert rev.revision_identifier == "v1.0.0"
    assert rev.total_files == 3
    assert rev.total_bytes > 0

    # Check artifacts created
    artifacts = service.list_artifacts(
        project.id, repository.id, rev.id, user=owner, limit=10, offset=0
    )
    assert len(artifacts) == 3
    paths = {a.path for a in artifacts}
    assert paths == {"README.md", "package.json", "src/main.py"}

    # Verify CAS storage keys
    for art in artifacts:
        assert art.storage_key.startswith("content/")
        assert len(art.content_hash) == 64


def test_trigger_ingestion_unauthorized_user(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Viewer or foreign user cannot trigger ingestion."""
    service, _, repository, _, viewer, foreign = _setup_service(db_session, tmp_path)

    zip_path = tmp_path / "repo.zip"
    _create_zip_file(zip_path, {"a.py": b"x=1"})

    request = TriggerIngestionRequest(
        repository_id=repository.id,
        source_reference=str(zip_path),
    )

    with pytest.raises(ProjectAccessDeniedError):
        service.trigger_ingestion(request, user=viewer)

    with pytest.raises(ProjectAccessDeniedError):
        service.trigger_ingestion(request, user=foreign)


def test_trigger_ingestion_repository_not_found(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Trigger ingestion on non-existent repository raises RepositoryNotFoundError."""
    service, _, _, owner, _, _ = _setup_service(db_session, tmp_path)

    request = TriggerIngestionRequest(
        repository_id=uuid4(),
        source_reference="some/path.zip",
    )

    with pytest.raises(RepositoryNotFoundError):
        service.trigger_ingestion(request, user=owner)


def test_trigger_ingestion_active_ingestion_guard(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Cannot start a new ingestion when one is already in processing status."""
    service, project, repository, owner, _, _ = _setup_service(db_session, tmp_path)

    # Manually simulate an active processing ingestion
    ingestion_repo = SqlAlchemyIngestionRepository(db_session)
    from backend.platform.ingestion.domain.ingestion import Ingestion

    now = datetime.now(UTC)
    active = Ingestion(
        id=uuid4(),
        project_id=project.id,
        repository_id=repository.id,
        source_type="archive",
        source_reference="some/path.zip",
        status=IngestionStatus.PROCESSING,
        error_code=None,
        error_message=None,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    ingestion_repo.save(active)

    request = TriggerIngestionRequest(
        repository_id=repository.id,
        source_reference=str(tmp_path / "new.zip"),
    )

    with pytest.raises(ActiveIngestionExistsError):
        service.trigger_ingestion(request, user=owner)


def test_trigger_ingestion_failure_records_failed_status(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Invalid archive causes ingestion to transition to FAILED with error code."""
    service, project, repository, owner, _, _ = _setup_service(db_session, tmp_path)

    fake_zip = tmp_path / "corrupt.zip"
    fake_zip.write_bytes(b"not a real zip")

    request = TriggerIngestionRequest(
        repository_id=repository.id,
        source_type="archive",
        source_reference=str(fake_zip),
    )

    with pytest.raises(SourceValidationError):
        service.trigger_ingestion(request, user=owner)

    # Check ingestion status in DB
    ingestions = service.list_ingestions(
        project.id, repository.id, user=owner, limit=10, offset=0
    )
    assert len(ingestions) == 1
    failed_job = ingestions[0]
    assert failed_job.status == "failed"
    assert failed_job.error_code == "source_validation_failed"
    assert "not a valid zip archive" in (failed_job.error_message or "")


def test_query_methods_and_project_isolation(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Test get_ingestion, list_ingestions, and cross-project isolation."""
    service, project, repository, owner, viewer, foreign = _setup_service(
        db_session, tmp_path
    )

    zip_path = tmp_path / "repo.zip"
    _create_zip_file(zip_path, {"src/app.py": b"print(1)"})

    request = TriggerIngestionRequest(
        repository_id=repository.id,
        source_reference=str(zip_path),
    )
    ingestion = service.trigger_ingestion(request, user=owner)

    # Viewer has read access
    fetched = service.get_ingestion(
        project.id, repository.id, ingestion.id, user=viewer
    )
    assert fetched.id == ingestion.id

    # Foreign user has no access
    with pytest.raises(ProjectAccessDeniedError):
        service.get_ingestion(project.id, repository.id, ingestion.id, user=foreign)

    with pytest.raises(ProjectAccessDeniedError):
        service.list_ingestions(
            project.id, repository.id, user=foreign, limit=10, offset=0
        )

    # Repository mismatch against authorized project raises RepositoryNotFoundError
    project_repo = SqlAlchemyProjectRepository(db_session)
    access_repo = SqlAlchemyProjectAccessRepository(db_session)
    access_service = ProjectAccessService(access_repo)
    now = datetime.now(UTC)
    project2 = project_repo.save(
        Project(
            id=uuid4(),
            name="Other-Project",
            description="Second project",
            created_at=now,
            updated_at=now,
        )
    )
    access_service.grant_access(project2.id, owner.id, ProjectRole.OWNER)

    with pytest.raises(RepositoryNotFoundError):
        service.get_ingestion(project2.id, repository.id, ingestion.id, user=owner)
