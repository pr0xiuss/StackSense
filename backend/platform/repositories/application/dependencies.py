"""Dependency providers for the Repository application layer."""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database_session
from backend.platform.projects.application.authorization import (
    ProjectAuthorization,
)
from backend.platform.projects.application.dependencies import (
    get_project_authorization,
)
from backend.platform.repositories.application.repository_service import (
    RepositoryService,
)
from backend.platform.repositories.application.service import (
    DefaultRepositoryService,
)
from backend.platform.repositories.infra.repository import (
    SqlAlchemyRepositoryRepository,
)


def get_repository_service(
    session: Session = Depends(get_database_session),
    authorization: ProjectAuthorization = Depends(get_project_authorization),
) -> Generator[RepositoryService]:
    """Provide the Repository application service for an API request."""
    repository = SqlAlchemyRepositoryRepository(session)
    yield DefaultRepositoryService(
        repository=repository,
        authorization=authorization,
    )
