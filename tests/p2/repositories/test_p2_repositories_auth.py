"""Project-scoped authorization tests for Repository operations."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database
from backend.platform.errors import ProjectAccessDeniedError
from backend.platform.identity.domain.user import User
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
    """Provide a database session for authorization integration testing."""
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


def _setup_project_with_roles(
    session: Session,
) -> tuple[
    Project,
    User,  # owner
    User,  # admin
    User,  # developer
    User,  # viewer
    User,  # unauthorized
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
    project = project_repo.save(
        Project(
            id=uuid4(),
            name=f"Auth-Project-{uuid4().hex[:6]}",
            description="Project for RBAC testing",
            created_at=now,
            updated_at=now,
        )
    )

    owner = User(uuid4())
    admin = User(uuid4())
    developer = User(uuid4())
    viewer = User(uuid4())
    unauthorized = User(uuid4())

    access_service.grant_access(project.id, owner.id, ProjectRole.OWNER)
    access_service.grant_access(project.id, admin.id, ProjectRole.ADMIN)
    access_service.grant_access(project.id, developer.id, ProjectRole.DEVELOPER)
    access_service.grant_access(project.id, viewer.id, ProjectRole.VIEWER)

    return project, owner, admin, developer, viewer, unauthorized, service


def test_owner_has_full_repository_access(db_session: Session) -> None:
    project, owner, _, _, _, _, service = _setup_project_with_roles(db_session)

    # Register
    repo = service.register(
        project.id,
        RegisterRepositoryRequest(name="owner-repo"),
        user=owner,
    )
    assert repo.name == "owner-repo"

    # Get
    fetched = service.get(project.id, repo.id, user=owner)
    assert fetched.id == repo.id

    # List
    listed = service.list_by_project(project.id, limit=10, offset=0, user=owner)
    assert any(r.id == repo.id for r in listed)

    # Update
    updated = service.update(
        project.id,
        repo.id,
        UpdateRepositoryRequest(description="Owner updated"),
        user=owner,
    )
    assert updated.description == "Owner updated"

    # Delete
    service.delete(project.id, repo.id, user=owner)


def test_admin_has_full_repository_access(db_session: Session) -> None:
    project, _, admin, _, _, _, service = _setup_project_with_roles(db_session)

    # Register
    repo = service.register(
        project.id,
        RegisterRepositoryRequest(name="admin-repo"),
        user=admin,
    )
    assert repo.name == "admin-repo"

    # Get
    fetched = service.get(project.id, repo.id, user=admin)
    assert fetched.id == repo.id

    # List
    listed = service.list_by_project(project.id, limit=10, offset=0, user=admin)
    assert any(r.id == repo.id for r in listed)

    # Update
    updated = service.update(
        project.id,
        repo.id,
        UpdateRepositoryRequest(description="Admin updated"),
        user=admin,
    )
    assert updated.description == "Admin updated"

    # Delete
    service.delete(project.id, repo.id, user=admin)


def test_developer_can_create_read_update_but_cannot_delete(
    db_session: Session,
) -> None:
    project, _, _, developer, _, _, service = _setup_project_with_roles(db_session)

    # Register
    repo = service.register(
        project.id,
        RegisterRepositoryRequest(name="dev-repo"),
        user=developer,
    )
    assert repo.name == "dev-repo"

    # Get
    fetched = service.get(project.id, repo.id, user=developer)
    assert fetched.id == repo.id

    # List
    listed = service.list_by_project(project.id, limit=10, offset=0, user=developer)
    assert any(r.id == repo.id for r in listed)

    # Update
    updated = service.update(
        project.id,
        repo.id,
        UpdateRepositoryRequest(description="Dev updated"),
        user=developer,
    )
    assert updated.description == "Dev updated"

    # Delete (Must be denied)
    with pytest.raises(ProjectAccessDeniedError):
        service.delete(project.id, repo.id, user=developer)


def test_viewer_can_read_and_list_only(db_session: Session) -> None:
    project, owner, _, _, viewer, _, service = _setup_project_with_roles(db_session)

    # Pre-create repo as owner
    repo = service.register(
        project.id,
        RegisterRepositoryRequest(name="viewer-test-repo"),
        user=owner,
    )

    # Viewer can Get
    fetched = service.get(project.id, repo.id, user=viewer)
    assert fetched.id == repo.id

    # Viewer can List
    listed = service.list_by_project(project.id, limit=10, offset=0, user=viewer)
    assert any(r.id == repo.id for r in listed)

    # Viewer CANNOT Register
    with pytest.raises(ProjectAccessDeniedError):
        service.register(
            project.id,
            RegisterRepositoryRequest(name="viewer-forbidden"),
            user=viewer,
        )

    # Viewer CANNOT Update
    with pytest.raises(ProjectAccessDeniedError):
        service.update(
            project.id,
            repo.id,
            UpdateRepositoryRequest(name="hacked"),
            user=viewer,
        )

    # Viewer CANNOT Delete
    with pytest.raises(ProjectAccessDeniedError):
        service.delete(project.id, repo.id, user=viewer)


def test_unauthorized_user_denied_on_all_operations(
    db_session: Session,
) -> None:
    project, owner, _, _, _, unauthorized, service = _setup_project_with_roles(
        db_session
    )

    repo = service.register(
        project.id,
        RegisterRepositoryRequest(name="secret-repo"),
        user=owner,
    )

    # Denied on Get
    with pytest.raises(ProjectAccessDeniedError):
        service.get(project.id, repo.id, user=unauthorized)

    # Denied on List
    with pytest.raises(ProjectAccessDeniedError):
        service.list_by_project(project.id, limit=10, offset=0, user=unauthorized)

    # Denied on Register
    with pytest.raises(ProjectAccessDeniedError):
        service.register(
            project.id,
            RegisterRepositoryRequest(name="rogue-repo"),
            user=unauthorized,
        )

    # Denied on Update
    with pytest.raises(ProjectAccessDeniedError):
        service.update(
            project.id,
            repo.id,
            UpdateRepositoryRequest(name="rogue-update"),
            user=unauthorized,
        )

    # Denied on Delete
    with pytest.raises(ProjectAccessDeniedError):
        service.delete(project.id, repo.id, user=unauthorized)


def test_missing_user_when_auth_configured_raises_denied(
    db_session: Session,
) -> None:
    project, owner, _, _, _, _, service = _setup_project_with_roles(db_session)

    # Omitting user when authorization is configured
    with pytest.raises(ProjectAccessDeniedError):
        service.register(
            project.id,
            RegisterRepositoryRequest(name="no-user-repo"),
            user=None,
        )

    with pytest.raises(ProjectAccessDeniedError):
        service.list_by_project(project.id, limit=10, offset=0, user=None)
