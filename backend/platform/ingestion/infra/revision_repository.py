"""PostgreSQL implementation of RevisionRepository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.ingestion.domain.revision import RepositoryRevision
from backend.platform.ingestion.infra.model import RevisionModel
from backend.platform.ingestion.repositories.revision_repo import (
    RevisionRepository,
)


class SqlAlchemyRevisionRepository(RevisionRepository):
    """PostgreSQL-backed implementation of RevisionRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, revision: RepositoryRevision) -> RepositoryRevision:
        model = RevisionModel(
            id=revision.id,
            project_id=revision.project_id,
            repository_id=revision.repository_id,
            ingestion_id=revision.ingestion_id,
            revision_identifier=revision.revision_identifier,
            source_hash=revision.source_hash,
            total_files=revision.total_files,
            total_bytes=revision.total_bytes,
            created_at=revision.created_at,
        )
        self._session.add(model)
        self._session.flush()
        return revision

    def get_by_id(self, revision_id: UUID) -> RepositoryRevision | None:
        statement = select(RevisionModel).where(
            RevisionModel.id == revision_id,
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
    ) -> list[RepositoryRevision]:
        statement = (
            select(RevisionModel)
            .where(RevisionModel.repository_id == repository_id)
            .order_by(RevisionModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = self._session.scalars(statement).all()
        return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(model: RevisionModel) -> RepositoryRevision:
        return RepositoryRevision(
            id=model.id,
            project_id=model.project_id,
            repository_id=model.repository_id,
            ingestion_id=model.ingestion_id,
            revision_identifier=model.revision_identifier,
            source_hash=model.source_hash,
            total_files=model.total_files,
            total_bytes=model.total_bytes,
            created_at=model.created_at,
        )
