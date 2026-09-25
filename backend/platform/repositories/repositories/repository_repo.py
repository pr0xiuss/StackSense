"""Repository persistence contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.repositories.domain.repository import Repository


class RepositoryRepository(ABC):
    """Persistence contract for Repository entities.

    The application layer depends on this abstraction rather than a concrete
    persistence implementation.
    """

    @abstractmethod
    def save(self, repository: Repository) -> Repository:
        """Persist a repository and return the persisted entity."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, repository_id: UUID) -> Repository | None:
        """Retrieve a repository by its identifier."""
        raise NotImplementedError

    @abstractmethod
    def get_by_project_and_name(
        self,
        project_id: UUID,
        name: str,
    ) -> Repository | None:
        """Retrieve a repository by project ID and unique name."""
        raise NotImplementedError

    @abstractmethod
    def list_by_project(
        self,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[Repository]:
        """List repositories for a project with deterministic pagination."""
        raise NotImplementedError

    @abstractmethod
    def update(self, repository: Repository) -> Repository:
        """Update an existing repository entity."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, repository_id: UUID) -> None:
        """Delete a repository by its identifier."""
        raise NotImplementedError
