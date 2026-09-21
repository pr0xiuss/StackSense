"""Project application service."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.platform.projects.application.access_service import ProjectAccessService
from backend.platform.projects.application.dto import (
    CreateProjectRequest,
    ProjectResponse,
)
from backend.platform.projects.domain.project import Project
from backend.platform.projects.domain.project_role import ProjectRole
from backend.platform.projects.repositories.project_repo import ProjectRepository


class DefaultProjectService:
    """Default application service for Project use cases."""

    def __init__(
        self,
        repository: ProjectRepository,
        access_service: ProjectAccessService,
    ) -> None:
        self._repository = repository
        self._access_service = access_service

    def create(
        self,
        request: CreateProjectRequest,
        owner_id: UUID,
    ) -> ProjectResponse:
        """Create a project and grant the creator OWNER access."""
        now = datetime.now(UTC)

        project = Project(
            id=uuid4(),
            name=request.name,
            description=request.description,
            created_at=now,
            updated_at=now,
        )

        persisted_project = self._repository.save(project)

        self._access_service.grant_access(
            project_id=persisted_project.id,
            user_id=owner_id,
            role=ProjectRole.OWNER,
        )

        return ProjectResponse.model_validate(
            persisted_project,
        )

    def get(
        self,
        project_id: UUID,
    ) -> ProjectResponse | None:
        """Retrieve a project by identifier."""
        project = self._repository.get_by_id(project_id)

        if project is None:
            return None

        return ProjectResponse.model_validate(project)

    def list_all(self) -> list[ProjectResponse]:
        """List all projects."""
        projects = self._repository.list_all()

        return [ProjectResponse.model_validate(project) for project in projects]

    def delete(
        self,
        project_id: UUID,
    ) -> None:
        """Delete a project."""
        self._repository.delete(project_id)

    def list_for_user(
        self,
        user_id: UUID,
    ) -> list[ProjectResponse]:
        """List projects the user has access to."""
        access_records = self._access_service.list_user_access(
            user_id,
        )

        projects: list[ProjectResponse] = []

        for access in access_records:
            project = self._repository.get_by_id(
                access.project_id,
            )

            if project is None:
                continue

            projects.append(
                ProjectResponse.model_validate(project),
            )

        return projects
