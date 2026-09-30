"""Persistence integration tests for M4 Ingestion repositories."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database
from backend.platform.errors import IngestionNotFoundError
from backend.platform.ingestion.domain.artifact import RepositoryArtifact
from backend.platform.ingestion.domain.constants import (
    ArtifactCategory,
    IngestionStatus,
    SupportLevel,
)
from backend.platform.ingestion.domain.ingestion import Ingestion
from backend.platform.ingestion.domain.revision import RepositoryRevision
from backend.platform.ingestion.infra.artifact_repository import (
    SqlAlchemyArtifactRepository,
)
from backend.platform.ingestion.infra.ingestion_repository import (
    SqlAlchemyIngestionRepository,
)
from backend.platform.ingestion.infra.revision_repository import (
    SqlAlchemyRevisionRepository,
)
from backend.platform.projects.domain.project import Project
from backend.platform.projects.infra.repository import (
    SqlAlchemyProjectRepository,
)
from backend.platform.repositories.domain.repository import Repository
from backend.platform.repositories.infra.repository import (
    SqlAlchemyRepositoryRepository,
)


@pytest.fixture
def db_session() -> Generator[Session]:
    """Provide a database session for persistence integration tests."""
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


def _create_project_and_repository(
    session: Session,
) -> tuple[Project, Repository]:
    """Helper to set up an authorized project and repository."""
    now = datetime.now(UTC)
    project_repo = SqlAlchemyProjectRepository(session)
    project = project_repo.save(
        Project(
            id=uuid4(),
            name=f"proj-{uuid4().hex[:8]}",
            description="Test project",
            created_at=now,
            updated_at=now,
        )
    )

    repo_repo = SqlAlchemyRepositoryRepository(session)
    repository = repo_repo.save(
        Repository(
            id=uuid4(),
            project_id=project.id,
            name=f"repo-{uuid4().hex[:8]}",
            description="Test repo",
            status="registered",
            created_at=now,
            updated_at=now,
        )
    )
    return project, repository


def test_ingestion_crud_and_status_update(db_session: Session) -> None:
    """Test saving, retrieving, and updating an Ingestion entity."""
    project, repository = _create_project_and_repository(db_session)
    ingestion_repo = SqlAlchemyIngestionRepository(db_session)

    now = datetime.now(UTC)
    ingestion_id = uuid4()
    ingestion = Ingestion(
        id=ingestion_id,
        project_id=project.id,
        repository_id=repository.id,
        source_type="archive",
        source_reference="s3://bucket/test.zip",
        status=IngestionStatus.PENDING,
        error_code=None,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )

    # 1. Save
    saved = ingestion_repo.save(ingestion)
    assert saved.id == ingestion_id

    # 2. Get by ID
    loaded = ingestion_repo.get_by_id(ingestion_id)
    assert loaded is not None
    assert loaded.id == ingestion_id
    assert loaded.status == IngestionStatus.PENDING
    assert loaded.source_type == "archive"

    # 3. Update to processing
    started_at = datetime.now(UTC)
    processing = Ingestion(
        id=ingestion_id,
        project_id=project.id,
        repository_id=repository.id,
        source_type="archive",
        source_reference="s3://bucket/test.zip",
        status=IngestionStatus.PROCESSING,
        error_code=None,
        error_message=None,
        started_at=started_at,
        completed_at=None,
        created_at=now,
        updated_at=started_at,
    )
    updated = ingestion_repo.update(processing)
    assert updated.status == IngestionStatus.PROCESSING
    assert updated.started_at is not None

    # 4. Update to completed
    completed_at = datetime.now(UTC)
    completed = Ingestion(
        id=ingestion_id,
        project_id=project.id,
        repository_id=repository.id,
        source_type="archive",
        source_reference="s3://bucket/test.zip",
        status=IngestionStatus.COMPLETED,
        error_code=None,
        error_message=None,
        started_at=started_at,
        completed_at=completed_at,
        created_at=now,
        updated_at=completed_at,
    )
    final = ingestion_repo.update(completed)
    assert final.status == IngestionStatus.COMPLETED
    assert final.completed_at is not None


def test_ingestion_update_non_existent_raises(db_session: Session) -> None:
    """Updating a non-existent ingestion raises IngestionNotFoundError."""
    ingestion_repo = SqlAlchemyIngestionRepository(db_session)
    now = datetime.now(UTC)
    ingestion = Ingestion(
        id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        source_type="archive",
        source_reference="s3://bucket/missing.zip",
        status=IngestionStatus.PROCESSING,
        error_code=None,
        error_message=None,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(IngestionNotFoundError):
        ingestion_repo.update(ingestion)


def test_active_ingestion_partial_unique_index(db_session: Session) -> None:
    """Verify concurrent processing ingestions for same repo are blocked."""
    project, repository = _create_project_and_repository(db_session)
    ingestion_repo = SqlAlchemyIngestionRepository(db_session)

    now = datetime.now(UTC)
    active1 = Ingestion(
        id=uuid4(),
        project_id=project.id,
        repository_id=repository.id,
        source_type="archive",
        source_reference="s3://bucket/1.zip",
        status=IngestionStatus.PROCESSING,
        error_code=None,
        error_message=None,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    ingestion_repo.save(active1)

    active2 = Ingestion(
        id=uuid4(),
        project_id=project.id,
        repository_id=repository.id,
        source_type="archive",
        source_reference="s3://bucket/2.zip",
        status=IngestionStatus.PROCESSING,
        error_code=None,
        error_message=None,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(IntegrityError):
        ingestion_repo.save(active2)

    db_session.rollback()


def test_revision_persistence_and_unique_constraint(
    db_session: Session,
) -> None:
    """Test saving revision, listing, and unique (repo, rev) constraint."""
    project, repository = _create_project_and_repository(db_session)
    rev_repo = SqlAlchemyRevisionRepository(db_session)

    now = datetime.now(UTC)
    rev_id = uuid4()
    rev = RepositoryRevision(
        id=rev_id,
        project_id=project.id,
        repository_id=repository.id,
        ingestion_id=None,
        revision_identifier="v1.0.0",
        source_hash="c" * 64,
        total_files=10,
        total_bytes=50000,
        created_at=now,
    )

    saved = rev_repo.save(rev)
    assert saved.id == rev_id

    loaded = rev_repo.get_by_id(rev_id)
    assert loaded is not None
    assert loaded.revision_identifier == "v1.0.0"
    assert loaded.total_files == 10

    # Duplicate revision_identifier for the same repository must raise IntegrityError
    dup_rev = RepositoryRevision(
        id=uuid4(),
        project_id=project.id,
        repository_id=repository.id,
        ingestion_id=None,
        revision_identifier="v1.0.0",
        source_hash="d" * 64,
        total_files=20,
        total_bytes=60000,
        created_at=now,
    )
    with pytest.raises(IntegrityError):
        rev_repo.save(dup_rev)

    db_session.rollback()


def test_artifact_batch_save_and_list_pagination(db_session: Session) -> None:
    """Test batch saving artifacts, deterministic listing, and pagination."""
    project, repository = _create_project_and_repository(db_session)
    rev_repo = SqlAlchemyRevisionRepository(db_session)
    artifact_repo = SqlAlchemyArtifactRepository(db_session)

    now = datetime.now(UTC)
    revision = rev_repo.save(
        RepositoryRevision(
            id=uuid4(),
            project_id=project.id,
            repository_id=repository.id,
            ingestion_id=None,
            revision_identifier="main-branch",
            source_hash="e" * 64,
            total_files=3,
            total_bytes=1500,
            created_at=now,
        )
    )

    artifacts = [
        RepositoryArtifact(
            id=uuid4(),
            project_id=project.id,
            repository_id=repository.id,
            revision_id=revision.id,
            path="src/z_last.py",
            size_bytes=500,
            content_hash="1" * 64,
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
            storage_key="keys/z_last.py",
            created_at=now,
        ),
        RepositoryArtifact(
            id=uuid4(),
            project_id=project.id,
            repository_id=repository.id,
            revision_id=revision.id,
            path="src/a_first.py",
            size_bytes=400,
            content_hash="2" * 64,
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
            storage_key="keys/a_first.py",
            created_at=now,
        ),
        RepositoryArtifact(
            id=uuid4(),
            project_id=project.id,
            repository_id=repository.id,
            revision_id=revision.id,
            path="src/m_middle.py",
            size_bytes=600,
            content_hash="3" * 64,
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
            storage_key="keys/m_middle.py",
            created_at=now,
        ),
    ]

    artifact_repo.save_batch(artifacts)

    # Deterministic listing ordered by path asc
    listed = artifact_repo.list_by_revision(revision.id, limit=10, offset=0)
    assert len(listed) == 3
    assert listed[0].path == "src/a_first.py"
    assert listed[1].path == "src/m_middle.py"
    assert listed[2].path == "src/z_last.py"

    # Pagination: limit 1, offset 1
    page2 = artifact_repo.list_by_revision(revision.id, limit=1, offset=1)
    assert len(page2) == 1
    assert page2[0].path == "src/m_middle.py"


def test_artifact_unique_rev_path_constraint(db_session: Session) -> None:
    """Duplicate (revision_id, path) must raise IntegrityError."""
    project, repository = _create_project_and_repository(db_session)
    rev_repo = SqlAlchemyRevisionRepository(db_session)
    artifact_repo = SqlAlchemyArtifactRepository(db_session)

    now = datetime.now(UTC)
    revision = rev_repo.save(
        RepositoryRevision(
            id=uuid4(),
            project_id=project.id,
            repository_id=repository.id,
            ingestion_id=None,
            revision_identifier="v2.0.0",
            source_hash="f" * 64,
            total_files=1,
            total_bytes=100,
            created_at=now,
        )
    )

    art1 = RepositoryArtifact(
        id=uuid4(),
        project_id=project.id,
        repository_id=repository.id,
        revision_id=revision.id,
        path="README.md",
        size_bytes=100,
        content_hash="4" * 64,
        category=ArtifactCategory.DOCUMENTATION,
        support_level=SupportLevel.FULL,
        storage_key="keys/readme.md",
        created_at=now,
    )
    artifact_repo.save_batch([art1])

    art2 = RepositoryArtifact(
        id=uuid4(),
        project_id=project.id,
        repository_id=repository.id,
        revision_id=revision.id,
        path="README.md",  # duplicate path in same revision
        size_bytes=200,
        content_hash="5" * 64,
        category=ArtifactCategory.DOCUMENTATION,
        support_level=SupportLevel.FULL,
        storage_key="keys/readme2.md",
        created_at=now,
    )

    with pytest.raises(IntegrityError):
        artifact_repo.save_batch([art2])

    db_session.rollback()


def test_cascade_delete_from_repository(db_session: Session) -> None:
    """Deleting a repository cascades and cleans up ingestions, revisions, artifacts."""
    project, repository = _create_project_and_repository(db_session)
    ingestion_repo = SqlAlchemyIngestionRepository(db_session)
    rev_repo = SqlAlchemyRevisionRepository(db_session)
    artifact_repo = SqlAlchemyArtifactRepository(db_session)
    repo_repo = SqlAlchemyRepositoryRepository(db_session)

    now = datetime.now(UTC)
    ingestion = ingestion_repo.save(
        Ingestion(
            id=uuid4(),
            project_id=project.id,
            repository_id=repository.id,
            source_type="archive",
            source_reference="s3://bucket/test.zip",
            status=IngestionStatus.COMPLETED,
            error_code=None,
            error_message=None,
            started_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
    )

    revision = rev_repo.save(
        RepositoryRevision(
            id=uuid4(),
            project_id=project.id,
            repository_id=repository.id,
            ingestion_id=ingestion.id,
            revision_identifier="v1.0",
            source_hash="a" * 64,
            total_files=1,
            total_bytes=100,
            created_at=now,
        )
    )

    artifact_repo.save_batch(
        [
            RepositoryArtifact(
                id=uuid4(),
                project_id=project.id,
                repository_id=repository.id,
                revision_id=revision.id,
                path="index.js",
                size_bytes=100,
                content_hash="b" * 64,
                category=ArtifactCategory.SOURCE_CODE,
                support_level=SupportLevel.FULL,
                storage_key="keys/index.js",
                created_at=now,
            )
        ]
    )

    # Delete repository
    repo_repo.delete(repository.id)

    # Verify children are gone
    assert ingestion_repo.get_by_id(ingestion.id) is None
    assert rev_repo.get_by_id(revision.id) is None
    assert len(artifact_repo.list_by_revision(revision.id, limit=10, offset=0)) == 0


def test_ingestion_status_check_constraint(db_session: Session) -> None:
    """Verify ck_ingestions_status rejects status values outside allowed set."""
    from backend.platform.ingestion.infra.model import IngestionModel

    project, repository = _create_project_and_repository(db_session)
    now = datetime.now(UTC)

    invalid_model = IngestionModel(
        id=uuid4(),
        project_id=project.id,
        repository_id=repository.id,
        source_type="archive",
        source_reference="s3://bucket/test.zip",
        status="bogus_status",
        error_code=None,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(invalid_model)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()
