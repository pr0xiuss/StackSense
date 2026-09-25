"""Unit and integration tests for DefaultRepositoryService."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database
from backend.platform.errors import (
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
)
from backend.platform.projects.domain.project import Project
from backend.platform.projects.infra.repository import (
    SqlAlchemyProjectRepository,
)
from backend.platform.repositories.application.dto import (
    RegisterRepositoryRequest,
    UpdateRepositoryRequest,
)
from backend.platform.repositories.application.service import (
    DefaultRepositoryService,
)
from backend.platform.repositories.domain.repository import Repository
from backend.platform.repositories.infra.repository import (
    SqlAlchemyRepositoryRepository,
)
from backend.platform.repositories.repositories.repository_repo import (
    RepositoryRepository,
)


@pytest.fixture
def db_session() -> Generator[Session]:
    """Provide a database session for service testing."""
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


def _create_project(session: Session, name: str = "Service Test Project") -> Project:
    project_repo = SqlAlchemyProjectRepository(session)
    now = datetime.now(UTC)
    project = Project(
        id=uuid4(),
        name=name,
        description="Project for service tests",
        created_at=now,
        updated_at=now,
    )
    return project_repo.save(project)


def test_register_repository_success(db_session: Session) -> None:
    project = _create_project(db_session, "Register Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    request = RegisterRepositoryRequest(
        name="web-frontend",
        description="Next.js web application",
    )
    response = service.register(project.id, request)

    assert response.id is not None
    assert response.project_id == project.id
    assert response.name == "web-frontend"
    assert response.description == "Next.js web application"
    assert response.status == "registered"
    assert isinstance(response.created_at, datetime)
    assert isinstance(response.updated_at, datetime)


def test_register_repository_without_description(db_session: Session) -> None:
    project = _create_project(db_session, "No Desc Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    request = RegisterRepositoryRequest(name="api-gateway")
    response = service.register(project.id, request)

    assert response.name == "api-gateway"
    assert response.description is None
    assert response.status == "registered"


def test_register_repository_duplicate_name_raises_conflict(
    db_session: Session,
) -> None:
    project = _create_project(db_session, "Duplicate Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    request = RegisterRepositoryRequest(name="service-a")
    service.register(project.id, request)

    duplicate_request = RegisterRepositoryRequest(name="service-a")
    with pytest.raises(RepositoryAlreadyExistsError):
        service.register(project.id, duplicate_request)


def test_register_repository_race_condition_integrity_error() -> None:
    class FailingRepo(RepositoryRepository):
        def save(self, repository: Repository) -> Repository:
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))

        def get_by_id(self, repository_id: UUID) -> Repository | None:
            return None

        def get_by_project_and_name(
            self, project_id: UUID, name: str
        ) -> Repository | None:
            return None

        def list_by_project(
            self, project_id: UUID, *, limit: int, offset: int
        ) -> list[Repository]:
            return []

        def update(self, repository: Repository) -> Repository:
            return repository

        def delete(self, repository_id: UUID) -> None:
            pass

    service = DefaultRepositoryService(repository=FailingRepo())
    request = RegisterRepositoryRequest(name="racing-service")

    with pytest.raises(RepositoryAlreadyExistsError):
        service.register(uuid4(), request)


def test_get_repository_success(db_session: Session) -> None:
    project = _create_project(db_session, "Get Repo Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    created = service.register(
        project.id,
        RegisterRepositoryRequest(name="catalog-service"),
    )

    retrieved = service.get(project.id, created.id)
    assert retrieved.id == created.id
    assert retrieved.name == "catalog-service"
    assert retrieved.project_id == project.id


def test_get_repository_nonexistent_raises_not_found(
    db_session: Session,
) -> None:
    project = _create_project(db_session, "Missing Repo Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    with pytest.raises(RepositoryNotFoundError):
        service.get(project.id, uuid4())


def test_get_repository_mismatched_project_raises_not_found(
    db_session: Session,
) -> None:
    project_a = _create_project(db_session, "Project A")
    project_b = _create_project(db_session, "Project B")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    repo_a = service.register(
        project_a.id,
        RegisterRepositoryRequest(name="app-a"),
    )

    with pytest.raises(RepositoryNotFoundError):
        service.get(project_b.id, repo_a.id)


def test_list_repositories_by_project_pagination(
    db_session: Session,
) -> None:
    project = _create_project(db_session, "List Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    for i in range(5):
        service.register(
            project.id,
            RegisterRepositoryRequest(name=f"repo-{i}"),
        )

    page1 = service.list_by_project(project.id, limit=2, offset=0)
    assert len(page1) == 2
    assert page1[0].name == "repo-0"
    assert page1[1].name == "repo-1"

    page2 = service.list_by_project(project.id, limit=2, offset=2)
    assert len(page2) == 2
    assert page2[0].name == "repo-2"
    assert page2[1].name == "repo-3"

    page3 = service.list_by_project(project.id, limit=2, offset=4)
    assert len(page3) == 1
    assert page3[0].name == "repo-4"


def test_list_repositories_empty_for_new_project(
    db_session: Session,
) -> None:
    project = _create_project(db_session, "Empty Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    repos = service.list_by_project(project.id, limit=10, offset=0)
    assert repos == []


def test_update_repository_success(db_session: Session) -> None:
    project = _create_project(db_session, "Update Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    created = service.register(
        project.id,
        RegisterRepositoryRequest(name="old-name", description="old desc"),
    )

    update_req = UpdateRepositoryRequest(
        name="new-name",
        description="new desc",
    )
    updated = service.update(project.id, created.id, update_req)

    assert updated.id == created.id
    assert updated.name == "new-name"
    assert updated.description == "new desc"
    assert updated.updated_at >= created.updated_at


def test_update_repository_name_conflict(db_session: Session) -> None:
    project = _create_project(db_session, "Conflict Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    service.register(project.id, RegisterRepositoryRequest(name="repo-one"))
    repo2 = service.register(project.id, RegisterRepositoryRequest(name="repo-two"))

    with pytest.raises(RepositoryAlreadyExistsError):
        service.update(
            project.id,
            repo2.id,
            UpdateRepositoryRequest(name="repo-one"),
        )


def test_update_repository_same_name_allowed(db_session: Session) -> None:
    project = _create_project(db_session, "Same Name Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    created = service.register(
        project.id,
        RegisterRepositoryRequest(name="stable-name", description="v1"),
    )

    updated = service.update(
        project.id,
        created.id,
        UpdateRepositoryRequest(name="stable-name", description="v2"),
    )
    assert updated.name == "stable-name"
    assert updated.description == "v2"


def test_update_repository_nonexistent_raises_not_found(
    db_session: Session,
) -> None:
    project = _create_project(db_session, "Missing Update Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    with pytest.raises(RepositoryNotFoundError):
        service.update(
            project.id,
            uuid4(),
            UpdateRepositoryRequest(name="whatever"),
        )


def test_update_repository_mismatched_project_raises_not_found(
    db_session: Session,
) -> None:
    project_a = _create_project(db_session, "Update Proj A")
    project_b = _create_project(db_session, "Update Proj B")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    repo_a = service.register(
        project_a.id,
        RegisterRepositoryRequest(name="app-a"),
    )

    with pytest.raises(RepositoryNotFoundError):
        service.update(
            project_b.id,
            repo_a.id,
            UpdateRepositoryRequest(name="hacked-name"),
        )


def test_delete_repository_success(db_session: Session) -> None:
    project = _create_project(db_session, "Delete Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    created = service.register(
        project.id,
        RegisterRepositoryRequest(name="to-delete"),
    )

    service.delete(project.id, created.id)

    with pytest.raises(RepositoryNotFoundError):
        service.get(project.id, created.id)


def test_delete_repository_nonexistent_raises_not_found(
    db_session: Session,
) -> None:
    project = _create_project(db_session, "Missing Delete Project")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    with pytest.raises(RepositoryNotFoundError):
        service.delete(project.id, uuid4())


def test_delete_repository_mismatched_project_raises_not_found(
    db_session: Session,
) -> None:
    project_a = _create_project(db_session, "Delete Proj A")
    project_b = _create_project(db_session, "Delete Proj B")
    repo_storage = SqlAlchemyRepositoryRepository(db_session)
    service = DefaultRepositoryService(repository=repo_storage)

    repo_a = service.register(
        project_a.id,
        RegisterRepositoryRequest(name="do-not-delete"),
    )

    with pytest.raises(RepositoryNotFoundError):
        service.delete(project_b.id, repo_a.id)

    # Verify repo_a is still intact
    assert service.get(project_a.id, repo_a.id).name == "do-not-delete"
