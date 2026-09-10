from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.platform.projects.application.dto import (
    CreateProjectRequest,
    ProjectResponse,
)
from backend.platform.projects.domain.project import Project
from backend.platform.projects.repositories.project_repo import (
    ProjectRepository,
)


class DefaultProjectService:
    """
    Default application service for Project use cases.

    Coordinates domain objects and persistence without exposing
    infrastructure details to the API layer.
    """

    def __init__(
        self,
        repository: ProjectRepository,
    ) -> None:
        self._repository = repository

    def create(
        self,
        request: CreateProjectRequest,
    ) -> ProjectResponse:
        now = datetime.now(UTC)

        project = Project(
            id=uuid4(),
            name=request.name,
            description=request.description,
            created_at=now,
            updated_at=now,
        )

        persisted_project = self._repository.save(project)

        return ProjectResponse.model_validate(
            persisted_project,
        )

    def get(
        self,
        project_id: UUID,
    ) -> ProjectResponse | None:
        project = self._repository.get_by_id(project_id)

        if project is None:
            return None

        return ProjectResponse.model_validate(project)

    def list_all(self) -> list[ProjectResponse]:
        projects = self._repository.list_all()

        return [ProjectResponse.model_validate(project) for project in projects]

    def delete(
        self,
        project_id: UUID,
    ) -> None:
        self._repository.delete(project_id)
