"""Project access API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from backend.platform.identity.application.dependencies import (
    get_current_user,
)
from backend.platform.identity.domain.user import User
from backend.platform.projects.application.access_dto import (
    GrantProjectAccessRequest,
    ProjectAccessResponse,
    UpdateProjectAccessRequest,
)
from backend.platform.projects.application.access_service import (
    ProjectAccessService,
)
from backend.platform.projects.application.authorization import (
    ProjectAuthorization,
)
from backend.platform.projects.application.dependencies import (
    get_project_access_service,
    get_project_authorization,
)

router = APIRouter(
    prefix="/projects/{project_id}/access",
    tags=["Project Access"],
)


@router.post(
    "",
    response_model=ProjectAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
def grant_project_access(
    project_id: UUID,
    request: GrantProjectAccessRequest,
    current_user: User = Depends(get_current_user),
    access_service: ProjectAccessService = Depends(
        get_project_access_service,
    ),
    authorization: ProjectAuthorization = Depends(
        get_project_authorization,
    ),
) -> ProjectAccessResponse:
    """Grant a user access to a project."""
    authorization.require_manage_access(
        project_id=project_id,
        user=current_user,
    )

    access = access_service.grant_access(
        project_id=project_id,
        user_id=request.user_id,
        role=request.role,
    )

    return ProjectAccessResponse.model_validate(access)


@router.patch(
    "/{user_id}",
    response_model=ProjectAccessResponse,
)
def update_project_access(
    project_id: UUID,
    user_id: UUID,
    request: UpdateProjectAccessRequest,
    current_user: User = Depends(get_current_user),
    access_service: ProjectAccessService = Depends(
        get_project_access_service,
    ),
    authorization: ProjectAuthorization = Depends(
        get_project_authorization,
    ),
) -> ProjectAccessResponse:
    """Change a user's role within a project."""
    authorization.require_manage_access(
        project_id=project_id,
        user=current_user,
    )

    access = access_service.change_role(
        project_id=project_id,
        user_id=user_id,
        role=request.role,
    )

    return ProjectAccessResponse.model_validate(access)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_project_access(
    project_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    access_service: ProjectAccessService = Depends(
        get_project_access_service,
    ),
    authorization: ProjectAuthorization = Depends(
        get_project_authorization,
    ),
) -> None:
    """Revoke a user's access to a project."""
    authorization.require_manage_access(
        project_id=project_id,
        user=current_user,
    )

    access_service.revoke_access(
        project_id=project_id,
        user_id=user_id,
    )
