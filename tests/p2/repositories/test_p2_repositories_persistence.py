"""Persistence integration tests for SqlAlchemyRepositoryRepository."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database
from backend.platform.errors import RepositoryNotFoundError
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
    """Provide a database session for persistence integration testing."""
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


def _create_project(session: Session, name: str = "Test Project") -> Project:
    project_repo = SqlAlchemyProjectRepository(session)
    now = datetime.now(UTC)
    project = Project(
        id=uuid4(),
        name=name,
        description="Test project description",
        created_at=now,
        updated_at=now,
    )
    return project_repo.save(project)


def test_save_and_get_by_id(db_session: Session) -> None:
    project = _create_project(db_session)
    repo = SqlAlchemyRepositoryRepository(db_session)

    now = datetime.now(UTC)
    repository = Repository(
        id=uuid4(),
        project_id=project.id,
        name="orders-api",
        description="Orders microservice",
        status="registered",
        created_at=now,
        updated_at=now,
    )

    saved = repo.save(repository)
    assert saved.id == repository.id

    fetched = repo.get_by_id(repository.id)
    assert fetched is not None
    assert fetched.id == repository.id
    assert fetched.project_id == project.id
    assert fetched.name == "orders-api"
    assert fetched.description == "Orders microservice"
    assert fetched.status == "registered"


def test_get_by_id_nonexistent(db_session: Session) -> None:
    repo = SqlAlchemyRepositoryRepository(db_session)
    result = repo.get_by_id(uuid4())
    assert result is None


def test_get_by_project_and_name(db_session: Session) -> None:
    project = _create_project(db_session)
    repo = SqlAlchemyRepositoryRepository(db_session)

    now = datetime.now(UTC)
    repository = Repository(
        id=uuid4(),
        project_id=project.id,
        name="billing-worker",
        description=None,
        status="registered",
        created_at=now,
        updated_at=now,
    )
    repo.save(repository)

    fetched = repo.get_by_project_and_name(project.id, "billing-worker")
    assert fetched is not None
    assert fetched.id == repository.id
    assert fetched.name == "billing-worker"

    nonexistent = repo.get_by_project_and_name(project.id, "other-worker")
    assert nonexistent is None


def test_list_by_project_with_pagination(db_session: Session) -> None:
    project = _create_project(db_session)
    repo = SqlAlchemyRepositoryRepository(db_session)

    now = datetime.now(UTC)
    for i in range(3):
        repo.save(
            Repository(
                id=uuid4(),
                project_id=project.id,
                name=f"repo-{i}",
                description=None,
                status="registered",
                created_at=now,
                updated_at=now,
            )
        )

    # First page
    page1 = repo.list_by_project(project.id, limit=2, offset=0)
    assert len(page1) == 2

    # Second page
    page2 = repo.list_by_project(project.id, limit=2, offset=2)
    assert len(page2) == 1

    # Empty page beyond count
    page3 = repo.list_by_project(project.id, limit=2, offset=10)
    assert len(page3) == 0


def test_update_repository(db_session: Session) -> None:
    project = _create_project(db_session)
    repo = SqlAlchemyRepositoryRepository(db_session)

    now = datetime.now(UTC)
    repository = Repository(
        id=uuid4(),
        project_id=project.id,
        name="catalog-service",
        description="Initial description",
        status="registered",
        created_at=now,
        updated_at=now,
    )
    repo.save(repository)

    later = datetime.now(UTC)
    updated_entity = Repository(
        id=repository.id,
        project_id=project.id,
        name="catalog-service-v2",
        description="Updated description",
        status="active",
        created_at=now,
        updated_at=later,
    )

    result = repo.update(updated_entity)
    assert result.name == "catalog-service-v2"
    assert result.description == "Updated description"
    assert result.status == "active"

    fetched = repo.get_by_id(repository.id)
    assert fetched is not None
    assert fetched.name == "catalog-service-v2"
    assert fetched.description == "Updated description"
    assert fetched.status == "active"


def test_update_nonexistent_repository_raises_error(
    db_session: Session,
) -> None:
    repo = SqlAlchemyRepositoryRepository(db_session)
    now = datetime.now(UTC)
    repository = Repository(
        id=uuid4(),
        project_id=uuid4(),
        name="missing",
        description=None,
        status="registered",
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(RepositoryNotFoundError):
        repo.update(repository)


def test_delete_repository(db_session: Session) -> None:
    project = _create_project(db_session)
    repo = SqlAlchemyRepositoryRepository(db_session)

    now = datetime.now(UTC)
    repository = Repository(
        id=uuid4(),
        project_id=project.id,
        name="to-delete",
        description=None,
        status="registered",
        created_at=now,
        updated_at=now,
    )
    repo.save(repository)
    assert repo.get_by_id(repository.id) is not None

    repo.delete(repository.id)
    assert repo.get_by_id(repository.id) is None


def test_unique_constraint_on_project_id_and_name(db_session: Session) -> None:
    project = _create_project(db_session)
    repo = SqlAlchemyRepositoryRepository(db_session)

    now = datetime.now(UTC)
    repo1 = Repository(
        id=uuid4(),
        project_id=project.id,
        name="duplicate-test",
        description=None,
        status="registered",
        created_at=now,
        updated_at=now,
    )
    repo.save(repo1)

    repo2 = Repository(
        id=uuid4(),
        project_id=project.id,
        name="duplicate-test",
        description=None,
        status="registered",
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(IntegrityError):
        repo.save(repo2)

    db_session.rollback()


def test_cascade_delete_on_project_delete(db_session: Session) -> None:
    project_repo = SqlAlchemyProjectRepository(db_session)
    repo = SqlAlchemyRepositoryRepository(db_session)

    now = datetime.now(UTC)
    project = Project(
        id=uuid4(),
        name="Project To Cascade",
        description=None,
        created_at=now,
        updated_at=now,
    )
    project_repo.save(project)

    repository = Repository(
        id=uuid4(),
        project_id=project.id,
        name="child-repo",
        description=None,
        status="registered",
        created_at=now,
        updated_at=now,
    )
    repo.save(repository)
    assert repo.get_by_id(repository.id) is not None

    # Delete parent project
    project_repo.delete(project.id)

    # Repository must be deleted due to ON DELETE CASCADE
    assert repo.get_by_id(repository.id) is None
