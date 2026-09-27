"""PostgreSQL implementation of IngestionRepository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.errors import IngestionNotFoundError
from backend.platform.ingestion.domain.constants import IngestionStatus
from backend.platform.ingestion.domain.ingestion import Ingestion
from backend.platform.ingestion.infra.model import IngestionModel
from backend.platform.ingestion.repositories.ingestion_repo import (
    IngestionRepository,
)


class SqlAlchemyIngestionRepository(IngestionRepository):
    """PostgreSQL-backed implementation of IngestionRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, ingestion: Ingestion) -> Ingestion:
        model = IngestionModel(
            id=ingestion.id,
            project_id=ingestion.project_id,
            repository_id=ingestion.repository_id,
            source_type=ingestion.source_type,
            source_reference=ingestion.source_reference,
            status=ingestion.status.value,
            error_code=ingestion.error_code,
            error_message=ingestion.error_message,
            started_at=ingestion.started_at,
            completed_at=ingestion.completed_at,
            created_at=ingestion.created_at,
            updated_at=ingestion.updated_at,
        )
        self._session.add(model)
        self._session.flush()
        return ingestion

    def update(self, ingestion: Ingestion) -> Ingestion:
        model = self._session.get(IngestionModel, ingestion.id)
        if model is None:
            raise IngestionNotFoundError()

        model.status = ingestion.status.value
        model.error_code = ingestion.error_code
        model.error_message = ingestion.error_message
        model.started_at = ingestion.started_at
        model.completed_at = ingestion.completed_at
        model.updated_at = ingestion.updated_at

        self._session.flush()
        return self._to_domain(model)

    def get_by_id(self, ingestion_id: UUID) -> Ingestion | None:
        statement = select(IngestionModel).where(
            IngestionModel.id == ingestion_id,
        )
        model = self._session.scalar(statement)
        if model is None:
            return None
        return self._to_domain(model)

    def list_by_repository(
        self,
        repository_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[Ingestion]:
        statement = (
            select(IngestionModel)
            .where(IngestionModel.repository_id == repository_id)
            .order_by(IngestionModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = self._session.scalars(statement).all()
        return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(model: IngestionModel) -> Ingestion:
        return Ingestion(
            id=model.id,
            project_id=model.project_id,
            repository_id=model.repository_id,
            source_type=model.source_type,
            source_reference=model.source_reference,
            status=IngestionStatus(model.status),
            error_code=model.error_code,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
