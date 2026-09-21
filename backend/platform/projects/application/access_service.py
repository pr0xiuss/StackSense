"""Project access application service."""

from uuid import UUID

from backend.platform.errors import (
    ProjectAccessAlreadyExistsError,
    ProjectAccessNotFoundError,
)
from backend.platform.projects.domain.project_access import ProjectAccess
from backend.platform.projects.domain.project_role import ProjectRole
from backend.platform.projects.repositories.project_access_repo import (
    ProjectAccessRepository,
)


class ProjectAccessService:
    """Coordinate project access use cases."""

    def __init__(
        self,
        repository: ProjectAccessRepository,
    ) -> None:
        self._repository = repository

    def get_access(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> ProjectAccess | None:
        return self._repository.get(
            project_id,
            user_id,
        )

    def list_project_access(
        self,
        project_id: UUID,
    ) -> list[ProjectAccess]:
        return self._repository.list_for_project(project_id)

    def revoke_access(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> None:
        """Revoke a user's access to a project."""
        access = self._repository.get(
            project_id,
            user_id,
        )

        if access is None:
            raise ProjectAccessNotFoundError()

        self._repository.delete(
            project_id,
            user_id,
        )

    def list_user_access(
        self,
        user_id: UUID,
    ) -> list[ProjectAccess]:
        """List all project access records for a user."""
        return self._repository.list_for_user(user_id)

    def change_role(
        self,
        project_id: UUID,
        user_id: UUID,
        role: ProjectRole,
    ) -> ProjectAccess:
        """Change a user's role within a project."""
        access = self._repository.get(
            project_id,
            user_id,
        )

        if access is None:
            raise ProjectAccessNotFoundError()

        return self._repository.update_role(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )

    def grant_access(
        self,
        project_id: UUID,
        user_id: UUID,
        role: ProjectRole,
    ) -> ProjectAccess:
        """Grant a user access to a project."""
        existing_access = self._repository.get(
            project_id,
            user_id,
        )

        if existing_access is not None:
            raise ProjectAccessAlreadyExistsError()

        access = ProjectAccess(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )

        return self._repository.save(access)
