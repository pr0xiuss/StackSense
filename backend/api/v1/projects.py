"""Project API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.platform.errors import ProjectAccessDeniedError
from backend.platform.identity.application.dependencies import (
    get_current_user,
)
from backend.platform.identity.domain.user import User
from backend.platform.projects.application.authorization import (
    ProjectAuthorization,
)
from backend.platform.projects.application.dependencies import (
    get_project_authorization,
    get_project_service,
)
from backend.platform.projects.application.dto import (
    CreateProjectRequest,
    ProjectResponse,
)
from backend.platform.projects.application.project_service import ProjectService
from backend.platform.projects.application.service import DefaultProjectService

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    request: CreateProjectRequest,
    current_user: User = Depends(get_current_user),
    service: DefaultProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Create a new project for the current user."""

    return service.create(
        request,
        current_user.id,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    service: DefaultProjectService = Depends(get_project_service),
    authorization: ProjectAuthorization = Depends(
        get_project_authorization,
    ),
) -> ProjectResponse:
    """Retrieve a project accessible to the current user."""

    project = service.get(project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    try:
        authorization.require_access(
            project_id=project_id,
            user=current_user,
        )
    except ProjectAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from None

    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> list[ProjectResponse]:
    """List projects accessible to the current user."""

    projects = service.list_all(
        current_user.id,
        limit=limit,
        offset=offset,
    )

    return [ProjectResponse.model_validate(project) for project in projects]


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    service: DefaultProjectService = Depends(get_project_service),
    authorization: ProjectAuthorization = Depends(
        get_project_authorization,
    ),
) -> None:
    """Delete a project when the current user has permission."""
    project = service.get(project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    authorization.require_delete_access(
        project_id=project_id,
        user=current_user,
    )

    service.delete(project_id)
