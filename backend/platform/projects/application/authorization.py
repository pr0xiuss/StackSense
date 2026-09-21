"""Project authorization helpers."""

from uuid import UUID

from backend.platform.errors import ProjectAccessDeniedError
from backend.platform.identity.domain.user import User
from backend.platform.projects.application.access_service import (
    ProjectAccessService,
)
from backend.platform.projects.domain.project_access import ProjectAccess
from backend.platform.projects.domain.project_role import ProjectRole


class ProjectAuthorization:
    """Authorize a user against a project."""

    def __init__(
        self,
        access_service: ProjectAccessService,
    ) -> None:
        self._access_service = access_service

    def get_access(
        self,
        project_id: UUID,
        user: User,
    ) -> ProjectAccess | None:
        """Return the user's access to a project."""
        return self._access_service.get_access(
            project_id=project_id,
            user_id=user.id,
        )

    def require_access(
        self,
        project_id: UUID,
        user: User,
    ) -> ProjectAccess:
        """Require the user to have access to a project."""
        access = self.get_access(
            project_id=project_id,
            user=user,
        )

        if access is None:
            raise ProjectAccessDeniedError()

        return access

    def require_delete_access(
        self,
        project_id: UUID,
        user: User,
    ) -> ProjectAccess:
        """Require the user to have project deletion permission."""
        access = self.require_access(
            project_id=project_id,
            user=user,
        )

        if not access.can_delete():
            raise ProjectAccessDeniedError()

        return access

    def require_update_access(
        self,
        project_id: UUID,
        user: User,
    ) -> ProjectAccess:
        """Require the user to have project update permission."""
        access = self.require_access(
            project_id=project_id,
            user=user,
        )

        if not access.can_update():
            raise ProjectAccessDeniedError()

        return access

    def require_create_access(
        self,
        project_id: UUID,
        user: User,
    ) -> ProjectAccess:
        """Require the user to have project create permission."""
        access = self.require_access(
            project_id=project_id,
            user=user,
        )

        if not access.can_create():
            raise ProjectAccessDeniedError()

        return access

    def require_manage_access(
        self,
        project_id: UUID,
        user: User,
    ) -> ProjectAccess:
        """Require permission to manage project access."""
        access = self.require_access(
            project_id=project_id,
            user=user,
        )

        if access.role not in {
            ProjectRole.OWNER,
            ProjectRole.ADMIN,
        }:
            raise ProjectAccessDeniedError()

        return access
