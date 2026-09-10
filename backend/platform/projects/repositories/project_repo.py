from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.projects.domain.project import Project


class ProjectRepository(ABC):
    """
    Persistence contract for Project entities.

    The application layer depends on this abstraction rather
    than a concrete persistence implementation.
    """

    @abstractmethod
    def save(
        self,
        project: Project,
    ) -> Project:
        """Persist a project and return the persisted entity."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(
        self,
        project_id: UUID,
    ) -> Project | None:
        """Retrieve a project by its identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[Project]:
        """Return all projects visible to the repository boundary."""
        raise NotImplementedError

    @abstractmethod
    def delete(
        self,
        project_id: UUID,
    ) -> None:
        """Delete a project by its identifier."""
        raise NotImplementedError
