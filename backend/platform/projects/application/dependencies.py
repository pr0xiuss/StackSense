"""Dependency providers for the Project application layer."""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database_session
from backend.platform.projects.application.service import DefaultProjectService
from backend.platform.projects.infra.repository import (
    SqlAlchemyProjectRepository,
)


def get_project_service(
    session: Session = Depends(get_database_session),
) -> Generator[DefaultProjectService]:
    """
    Provide the Project application service for an API request.

    The service receives a request-scoped database-backed repository.
    """

    repository = SqlAlchemyProjectRepository(session)

    yield DefaultProjectService(repository)
