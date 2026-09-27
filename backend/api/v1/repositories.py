"""Repository API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from backend.platform.identity.application.dependencies import (
    get_current_user,
)
from backend.platform.identity.domain.user import User
from backend.platform.repositories.application.dependencies import (
    get_repository_service,
)
from backend.platform.repositories.application.dto import (
    RegisterRepositoryRequest,
    RepositoryResponse,
    UpdateRepositoryRequest,
)
from backend.platform.repositories.application.repository_service import (
    RepositoryService,
)

router = APIRouter(
    prefix="/projects/{project_id}/repositories",
    tags=["Repositories"],
)


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_repository(
    project_id: UUID,
    request: RegisterRepositoryRequest,
    current_user: User = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    """Register a new repository under a project."""
    return service.register(
        project_id=project_id,
        request=request,
        user=current_user,
    )


@router.get(
    "",
    response_model=list[RepositoryResponse],
)
def list_repositories(
    project_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> list[RepositoryResponse]:
    """List repositories belonging to a project with pagination."""
    return service.list_by_project(
        project_id=project_id,
        limit=limit,
        offset=offset,
        user=current_user,
    )


@router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
)
def get_repository(
    project_id: UUID,
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    """Retrieve a repository by identifier within a project."""
    return service.get(
        project_id=project_id,
        repository_id=repository_id,
        user=current_user,
    )


@router.patch(
    "/{repository_id}",
    response_model=RepositoryResponse,
)
def update_repository(
    project_id: UUID,
    repository_id: UUID,
    request: UpdateRepositoryRequest,
    current_user: User = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    """Update repository metadata."""
    return service.update(
        project_id=project_id,
        repository_id=repository_id,
        request=request,
        user=current_user,
    )


@router.delete(
    "/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_repository(
    project_id: UUID,
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> None:
    """Delete a repository from a project."""
    service.delete(
        project_id=project_id,
        repository_id=repository_id,
        user=current_user,
    )
