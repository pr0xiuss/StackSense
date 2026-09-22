"""PostgreSQL implementation of the ProjectAccess repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.errors import ProjectAccessNotFoundError
from backend.platform.projects.domain.project_access import ProjectAccess
from backend.platform.projects.domain.project_role import ProjectRole
from backend.platform.projects.infra.access_model import ProjectAccessModel
from backend.platform.projects.repositories.project_access_repo import (
    ProjectAccessRepository,
)


class SqlAlchemyProjectAccessRepository(ProjectAccessRepository):
    """PostgreSQL-backed implementation of project access persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        access: ProjectAccess,
    ) -> ProjectAccess:
        model = ProjectAccessModel(
            project_id=access.project_id,
            user_id=access.user_id,
            role=access.role,
        )

        self._session.add(model)
        self._session.flush()

        return access

    def get(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> ProjectAccess | None:
        statement = select(ProjectAccessModel).where(
            ProjectAccessModel.project_id == project_id,
            ProjectAccessModel.user_id == user_id,
        )

        model = self._session.scalar(statement)

        if model is None:
            return None

        return self._to_domain(model)

    def list_for_project(
        self,
        project_id: UUID,
    ) -> list[ProjectAccess]:
        statement = (
            select(ProjectAccessModel)
            .where(ProjectAccessModel.project_id == project_id)
            .order_by(ProjectAccessModel.user_id)
        )

        models = self._session.scalars(statement).all()

        return [self._to_domain(model) for model in models]

    def list_for_user(
        self,
        user_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[ProjectAccess]:
        statement = (
            select(ProjectAccessModel)
            .where(ProjectAccessModel.user_id == user_id)
            .order_by(ProjectAccessModel.project_id)
            .offset(offset)
            .limit(limit)
        )

        models = self._session.scalars(statement).all()

        return [self._to_domain(model) for model in models]

    def delete(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> None:
        model = self._session.get(
            ProjectAccessModel,
            (project_id, user_id),
        )

        if model is not None:
            self._session.delete(model)
            self._session.flush()

    @staticmethod
    def _to_domain(
        model: ProjectAccessModel,
    ) -> ProjectAccess:
        return ProjectAccess(
            project_id=model.project_id,
            user_id=model.user_id,
            role=model.role,
        )

    def update_role(
        self,
        project_id: UUID,
        user_id: UUID,
        role: ProjectRole,
    ) -> ProjectAccess:
        model = self._session.get(
            ProjectAccessModel,
            (project_id, user_id),
        )

        if model is None:
            raise ProjectAccessNotFoundError()

        model.role = role
        self._session.flush()

        return self._to_domain(model)
