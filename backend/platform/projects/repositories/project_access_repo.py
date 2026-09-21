"""Project access repository contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.projects.domain.project_access import ProjectAccess
from backend.platform.projects.domain.project_role import ProjectRole


class ProjectAccessRepository(ABC):
    """Persistence contract for project access records."""

    @abstractmethod
    def save(self, access: ProjectAccess) -> ProjectAccess:
        """Persist a project access record."""
        ...

    @abstractmethod
    def get(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> ProjectAccess | None:
        """Retrieve a user's access to a project."""
        ...

    @abstractmethod
    def list_for_project(
        self,
        project_id: UUID,
    ) -> list[ProjectAccess]:
        """List all access records for a project."""
        ...

    @abstractmethod
    def list_for_user(
        self,
        user_id: UUID,
    ) -> list[ProjectAccess]:
        """List all project access records for a user."""
        ...

    @abstractmethod
    def delete(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> None:
        """Remove a user's access to a project."""
        ...

    @abstractmethod
    def update_role(
        self,
        project_id: UUID,
        user_id: UUID,
        role: ProjectRole,
    ) -> ProjectAccess:
        """Update a user's role within a project."""
        ...
