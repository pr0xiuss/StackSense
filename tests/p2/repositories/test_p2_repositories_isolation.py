"""Cross-Project isolation and tenancy boundary tests for Repositories."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database
from backend.platform.errors import RepositoryNotFoundError
from backend.platform.identity.domain.user import User
from backend.platform.identity.infra.user_repo import SqlAlchemyUserRepository
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
from backend.platform.repositories.application.dto import (
    RegisterRepositoryRequest,
    UpdateRepositoryRequest,
)
from backend.platform.repositories.application.service import (
    DefaultRepositoryService,
)
from backend.platform.repositories.infra.repository import (
    SqlAlchemyRepositoryRepository,
)


@pytest.fixture
def db_session() -> Generator[Session]:
    """Provide a database session for isolation testing."""
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


def _create_isolated_environment(
    session: Session,
) -> tuple[
    Project,
    User,
    Project,
    User,
    DefaultRepositoryService,
]:
    project_repo = SqlAlchemyProjectRepository(session)
    access_repo = SqlAlchemyProjectAccessRepository(session)
    access_service = ProjectAccessService(access_repo)
    authorization = ProjectAuthorization(access_service)
    repository_storage = SqlAlchemyRepositoryRepository(session)
    service = DefaultRepositoryService(
        repository=repository_storage,
        authorization=authorization,
    )

    now = datetime.now(UTC)
    project_a = project_repo.save(
        Project(
            id=uuid4(),
            name=f"Project-A-{uuid4().hex[:6]}",
            description="Tenant A",
            created_at=now,
            updated_at=now,
        )
    )
    user_repo = SqlAlchemyUserRepository(session)
    user_a = user_repo.save(
        User(
            id=uuid4(),
            email=f"user-a-{uuid4().hex[:6]}@stacksense.local",
            created_at=now,
            updated_at=now,
        )
    )
    access_service.grant_access(project_a.id, user_a.id, ProjectRole.OWNER)

    project_b = project_repo.save(
        Project(
            id=uuid4(),
            name=f"Project-B-{uuid4().hex[:6]}",
            description="Tenant B",
            created_at=now,
            updated_at=now,
        )
    )
    user_b = user_repo.save(
        User(
            id=uuid4(),
            email=f"user-b-{uuid4().hex[:6]}@stacksense.local",
            created_at=now,
            updated_at=now,
        )
    )
    access_service.grant_access(project_b.id, user_b.id, ProjectRole.OWNER)

    return project_a, user_a, project_b, user_b, service


def test_cross_project_isolation_get_returns_not_found(
    db_session: Session,
) -> None:
    project_a, user_a, project_b, user_b, service = _create_isolated_environment(
        db_session
    )

    # User B registers repository in Project B
    repo_b = service.register(
        project_b.id,
        RegisterRepositoryRequest(name="tenant-b-repo"),
        user=user_b,
    )

    # User A tries to access repo_b via Project A
    with pytest.raises(RepositoryNotFoundError):
        service.get(project_a.id, repo_b.id, user=user_a)


def test_cross_project_isolation_update_returns_not_found(
    db_session: Session,
) -> None:
    project_a, user_a, project_b, user_b, service = _create_isolated_environment(
        db_session
    )

    repo_b = service.register(
        project_b.id,
        RegisterRepositoryRequest(
            name="tenant-b-secret",
            description="Original B description",
        ),
        user=user_b,
    )

    # User A tries to update repo_b via Project A
    with pytest.raises(RepositoryNotFoundError):
        service.update(
            project_a.id,
            repo_b.id,
            UpdateRepositoryRequest(name="tampered-name"),
            user=user_a,
        )

    # Verify repo_b remains untouched in Project B
    unmodified = service.get(project_b.id, repo_b.id, user=user_b)
    assert unmodified.name == "tenant-b-secret"
    assert unmodified.description == "Original B description"


def test_cross_project_isolation_delete_returns_not_found(
    db_session: Session,
) -> None:
    project_a, user_a, project_b, user_b, service = _create_isolated_environment(
        db_session
    )

    repo_b = service.register(
        project_b.id,
        RegisterRepositoryRequest(name="tenant-b-safe"),
        user=user_b,
    )

    # User A tries to delete repo_b via Project A
    with pytest.raises(RepositoryNotFoundError):
        service.delete(project_a.id, repo_b.id, user=user_a)

    # Verify repo_b still exists in Project B
    assert service.get(project_b.id, repo_b.id, user=user_b).name == "tenant-b-safe"


def test_cross_project_isolation_list_does_not_leak_other_project_repositories(
    db_session: Session,
) -> None:
    project_a, user_a, project_b, user_b, service = _create_isolated_environment(
        db_session
    )

    for i in range(3):
        service.register(
            project_a.id,
            RegisterRepositoryRequest(name=f"proj-a-repo-{i}"),
            user=user_a,
        )
        service.register(
            project_b.id,
            RegisterRepositoryRequest(name=f"proj-b-repo-{i}"),
            user=user_b,
        )

    list_a = service.list_by_project(project_a.id, limit=50, offset=0, user=user_a)
    list_b = service.list_by_project(project_b.id, limit=50, offset=0, user=user_b)

    assert len(list_a) == 3
    assert all(r.project_id == project_a.id for r in list_a)
    assert all("proj-a-repo" in r.name for r in list_a)

    assert len(list_b) == 3
    assert all(r.project_id == project_b.id for r in list_b)
    assert all("proj-b-repo" in r.name for r in list_b)


def test_same_repository_name_in_different_projects_is_completely_independent(
    db_session: Session,
) -> None:
    project_a, user_a, project_b, user_b, service = _create_isolated_environment(
        db_session
    )

    # Both projects create a repository with the exact same name
    repo_a = service.register(
        project_a.id,
        RegisterRepositoryRequest(
            name="shared-name",
            description="Project A version",
        ),
        user=user_a,
    )

    repo_b = service.register(
        project_b.id,
        RegisterRepositoryRequest(
            name="shared-name",
            description="Project B version",
        ),
        user=user_b,
    )

    assert repo_a.id != repo_b.id
    assert repo_a.project_id == project_a.id
    assert repo_b.project_id == project_b.id
    assert repo_a.name == repo_b.name == "shared-name"
    assert repo_a.description == "Project A version"
    assert repo_b.description == "Project B version"

    # Modifying Project A does not affect Project B
    service.update(
        project_a.id,
        repo_a.id,
        UpdateRepositoryRequest(name="renamed-a"),
        user=user_a,
    )

    assert service.get(project_a.id, repo_a.id, user=user_a).name == "renamed-a"
    assert service.get(project_b.id, repo_b.id, user=user_b).name == "shared-name"

    # Deleting in Project A does not delete Project B
    service.delete(project_a.id, repo_a.id, user=user_a)
    with pytest.raises(RepositoryNotFoundError):
        service.get(project_a.id, repo_a.id, user=user_a)

    assert service.get(project_b.id, repo_b.id, user=user_b).name == "shared-name"
