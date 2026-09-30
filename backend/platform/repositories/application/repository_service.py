"""Repository application service contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.identity.domain.user import User
from backend.platform.repositories.application.dto import (
    RegisterRepositoryRequest,
    RepositoryResponse,
    UpdateRepositoryRequest,
)


class RepositoryService(ABC):
    """Application contract for Repository use cases.

    Covers repository registration, retrieval, listing, updates, and deletion
    strictly scoped within a Project boundary.
    """

    @abstractmethod
    def register(
        self,
        project_id: UUID,
        request: RegisterRepositoryRequest,
        user: User | None = None,
    ) -> RepositoryResponse:
        """Register a new repository under the specified project."""
        raise NotImplementedError

    @abstractmethod
    def get(
        self,
        project_id: UUID,
        repository_id: UUID,
        user: User | None = None,
    ) -> RepositoryResponse:
        """Retrieve a repository by identifier within a project."""
        raise NotImplementedError

    @abstractmethod
    def list_by_project(
        self,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        user: User | None = None,
    ) -> list[RepositoryResponse]:
        """List repositories belonging to a project with deterministic pagination."""
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        project_id: UUID,
        repository_id: UUID,
        request: UpdateRepositoryRequest,
        user: User | None = None,
    ) -> RepositoryResponse:
        """Update repository metadata within a project."""
        raise NotImplementedError

    @abstractmethod
    def delete(
        self,
        project_id: UUID,
        repository_id: UUID,
        user: User | None = None,
    ) -> None:
        """Delete a repository from a project."""
        raise NotImplementedError
