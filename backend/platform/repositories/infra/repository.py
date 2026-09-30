"""PostgreSQL implementation of the Repository repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.errors import RepositoryNotFoundError
from backend.platform.repositories.domain.repository import Repository
from backend.platform.repositories.infra.model import RepositoryModel
from backend.platform.repositories.repositories.repository_repo import (
    RepositoryRepository,
)


class SqlAlchemyRepositoryRepository(RepositoryRepository):
    """PostgreSQL-backed implementation of the RepositoryRepository contract."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        repository: Repository,
    ) -> Repository:
        model = RepositoryModel(
            id=repository.id,
            project_id=repository.project_id,
            name=repository.name,
            description=repository.description,
            status=repository.status,
            created_at=repository.created_at,
            updated_at=repository.updated_at,
        )

        self._session.add(model)
        self._session.flush()

        return repository

    def get_by_id(
        self,
        repository_id: UUID,
    ) -> Repository | None:
        statement = select(RepositoryModel).where(
            RepositoryModel.id == repository_id,
        )

        model = self._session.scalar(statement)

        if model is None:
            return None

        return self._to_domain(model)

    def get_by_project_and_name(
        self,
        project_id: UUID,
        name: str,
    ) -> Repository | None:
        statement = select(RepositoryModel).where(
            RepositoryModel.project_id == project_id,
            RepositoryModel.name == name,
        )

        model = self._session.scalar(statement)

        if model is None:
            return None

        return self._to_domain(model)

    def list_by_project(
        self,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[Repository]:
        statement = (
            select(RepositoryModel)
            .where(RepositoryModel.project_id == project_id)
            .order_by(RepositoryModel.created_at)
            .offset(offset)
            .limit(limit)
        )

        models = self._session.scalars(statement).all()

        return [self._to_domain(model) for model in models]

    def update(
        self,
        repository: Repository,
    ) -> Repository:
        model = self._session.get(
            RepositoryModel,
            repository.id,
        )

        if model is None:
            raise RepositoryNotFoundError()

        model.name = repository.name
        model.description = repository.description
        model.status = repository.status
        model.updated_at = repository.updated_at

        self._session.flush()

        return self._to_domain(model)

    def delete(
        self,
        repository_id: UUID,
    ) -> None:
        model = self._session.get(
            RepositoryModel,
            repository_id,
        )

        if model is not None:
            self._session.delete(model)
            self._session.flush()

    @staticmethod
    def _to_domain(
        model: RepositoryModel,
    ) -> Repository:
        return Repository(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            description=model.description,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
