"""PostgreSQL implementation of ArtifactRepository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.ingestion.domain.artifact import RepositoryArtifact
from backend.platform.ingestion.domain.constants import (
    ArtifactCategory,
    SupportLevel,
)
from backend.platform.ingestion.infra.model import ArtifactModel
from backend.platform.ingestion.repositories.artifact_repo import (
    ArtifactRepository,
)


class SqlAlchemyArtifactRepository(ArtifactRepository):
    """PostgreSQL-backed implementation of ArtifactRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_batch(self, artifacts: list[RepositoryArtifact]) -> None:
        if not artifacts:
            return

        models = [
            ArtifactModel(
                id=artifact.id,
                project_id=artifact.project_id,
                repository_id=artifact.repository_id,
                revision_id=artifact.revision_id,
                path=artifact.path,
                size_bytes=artifact.size_bytes,
                content_hash=artifact.content_hash,
                category=artifact.category.value,
                support_level=artifact.support_level.value,
                storage_key=artifact.storage_key,
                created_at=artifact.created_at,
            )
            for artifact in artifacts
        ]
        self._session.add_all(models)
        self._session.flush()

    def list_by_revision(
        self,
        revision_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[RepositoryArtifact]:
        statement = (
            select(ArtifactModel)
            .where(ArtifactModel.revision_id == revision_id)
            .order_by(ArtifactModel.path.asc())
            .offset(offset)
            .limit(limit)
        )
        models = self._session.scalars(statement).all()
        return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(model: ArtifactModel) -> RepositoryArtifact:
        return RepositoryArtifact(
            id=model.id,
            project_id=model.project_id,
            repository_id=model.repository_id,
            revision_id=model.revision_id,
            path=model.path,
            size_bytes=model.size_bytes,
            content_hash=model.content_hash,
            category=ArtifactCategory(model.category),
            support_level=SupportLevel(model.support_level),
            storage_key=model.storage_key,
            created_at=model.created_at,
        )
