"""Project API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.platform.projects.application.dependencies import (
    get_project_service,
)
from backend.platform.projects.application.dto import (
    CreateProjectRequest,
    ProjectResponse,
)
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
    service: DefaultProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Create a new project."""

    return service.create(request)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
def get_project(
    project_id: UUID,
    service: DefaultProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Retrieve a project by identifier."""

    project = service.get(project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


@router.get(
    "",
    response_model=list[ProjectResponse],
)
def list_projects(
    service: DefaultProjectService = Depends(get_project_service),
) -> list[ProjectResponse]:
    """List all projects."""

    return service.list_all()


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(
    project_id: UUID,
    service: DefaultProjectService = Depends(get_project_service),
) -> None:
    """Delete a project."""

    project = service.get(project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    service.delete(project_id)
