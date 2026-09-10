from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.projects.application.dto import (
    CreateProjectRequest,
    ProjectResponse,
)


class ProjectService(ABC):
    """
    Application contract for Project use cases.
    """

    @abstractmethod
    def create(
        self,
        request: CreateProjectRequest,
    ) -> ProjectResponse:
        """Create a new project."""
        raise NotImplementedError

    @abstractmethod
    def get(
        self,
        project_id: UUID,
    ) -> ProjectResponse | None:
        """Retrieve a project by identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[ProjectResponse]:
        """List all projects available to the caller."""
        raise NotImplementedError

    @abstractmethod
    def delete(
        self,
        project_id: UUID,
    ) -> None:
        """Delete a project."""
        raise NotImplementedError
