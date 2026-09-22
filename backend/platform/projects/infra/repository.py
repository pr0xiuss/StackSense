from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.projects.domain.project import Project
from backend.platform.projects.infra.model import ProjectModel
from backend.platform.projects.repositories.project_repo import (
    ProjectRepository,
)


class SqlAlchemyProjectRepository(ProjectRepository):
    """
    PostgreSQL-backed implementation of the ProjectRepository contract.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        project: Project,
    ) -> Project:
        model = ProjectModel(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

        self._session.add(model)
        self._session.flush()

        return project

    def get_by_id(
        self,
        project_id: UUID,
    ) -> Project | None:
        statement = select(ProjectModel).where(
            ProjectModel.id == project_id,
        )

        model = self._session.scalar(statement)

        if model is None:
            return None

        return self._to_domain(model)

    def list_all(self) -> list[Project]:
        statement = select(ProjectModel).order_by(
            ProjectModel.created_at,
        )

        models = self._session.scalars(statement).all()

        return [self._to_domain(model) for model in models]

    def delete(
        self,
        project_id: UUID,
    ) -> None:
        model = self._session.get(
            ProjectModel,
            project_id,
        )

        if model is not None:
            self._session.delete(model)
            self._session.flush()

    @staticmethod
    def _to_domain(
        model: ProjectModel,
    ) -> Project:
        return Project(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
