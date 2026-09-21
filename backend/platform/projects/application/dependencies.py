"""Dependency providers for the Project application layer."""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database_session
from backend.platform.projects.application.access_service import (
    ProjectAccessService,
)
from backend.platform.projects.application.authorization import (
    ProjectAuthorization,
)
from backend.platform.projects.application.service import (
    DefaultProjectService,
)
from backend.platform.projects.infra.access_repo import (
    SqlAlchemyProjectAccessRepository,
)
from backend.platform.projects.infra.repository import (
    SqlAlchemyProjectRepository,
)


def get_project_access_service(
    session: Session = Depends(get_database_session),
) -> Generator[ProjectAccessService]:
    """Provide the ProjectAccess application service."""

    repository = SqlAlchemyProjectAccessRepository(session)

    yield ProjectAccessService(repository)


def get_project_authorization(
    access_service: ProjectAccessService = Depends(
        get_project_access_service,
    ),
) -> ProjectAuthorization:
    """Provide the Project authorization component."""

    return ProjectAuthorization(access_service)


def get_project_service(
    session: Session = Depends(get_database_session),
) -> Generator[DefaultProjectService]:
    """
    Provide the Project application service for an API request.

    The service receives request-scoped database-backed repositories
    for Project and ProjectAccess operations.
    """

    project_repository = SqlAlchemyProjectRepository(session)

    access_repository = SqlAlchemyProjectAccessRepository(session)
    access_service = ProjectAccessService(access_repository)

    yield DefaultProjectService(
        repository=project_repository,
        access_service=access_service,
    )
