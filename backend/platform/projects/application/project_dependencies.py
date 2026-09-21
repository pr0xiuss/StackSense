"""Project-scoped dependency providers."""

from uuid import UUID

from fastapi import Depends

from backend.platform.identity.application.dependencies import (
    get_current_user,
)
from backend.platform.identity.domain.user import User
from backend.platform.projects.application.authorization import (
    ProjectAuthorization,
)
from backend.platform.projects.application.dependencies import (
    get_project_authorization,
)
from backend.platform.projects.domain.project_access import (
    ProjectAccess,
)


def require_project_access(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    authorization: ProjectAuthorization = Depends(
        get_project_authorization,
    ),
) -> ProjectAccess:
    """Require the current user to have access to a project."""
    return authorization.require_access(
        project_id=project_id,
        user=current_user,
    )
