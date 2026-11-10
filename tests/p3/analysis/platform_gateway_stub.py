"""Test-only adapter for legacy PostgreSQL Phase 1/2 fixtures."""

from uuid import UUID

from sqlalchemy.orm import Session

from backend.platform.analysis.application.platform_gateway import (
    PlatformArtifact,
    PlatformRepositoryGateway,
    PlatformSnapshotManifest,
)
from backend.platform.errors import AnalysisInputError
from backend.platform.ingestion.domain.constants import ArtifactCategory, SupportLevel
from backend.platform.ingestion.infra.model import ArtifactModel, RevisionModel


class SqlAlchemyTestPlatformGateway(PlatformRepositoryGateway):
    """Expose old test fixtures through the production platform port."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_manifest(
        self, project_id: UUID, repository_id: UUID, revision_id: UUID
    ) -> PlatformSnapshotManifest:
        revision = self._session.get(RevisionModel, revision_id)
        if (
            revision is None
            or revision.project_id != project_id
            or revision.repository_id != repository_id
        ):
            raise AnalysisInputError("Test revision does not match platform scope.")
        rows = (
            self._session.query(ArtifactModel)
            .filter(ArtifactModel.revision_id == revision_id)
            .order_by(ArtifactModel.path)
            .all()
        )
        artifacts = tuple(
            PlatformArtifact(
                id=row.id,
                project_id=row.project_id,
                repository_id=row.repository_id,
                revision_id=row.revision_id,
                path=row.path,
                size_bytes=row.size_bytes,
                content_hash=row.content_hash,
                category=ArtifactCategory(row.category),
                support_level=SupportLevel(row.support_level),
            )
            for row in rows
        )
        return PlatformSnapshotManifest(
            id=revision.id,
            project_id=revision.project_id,
            repository_id=revision.repository_id,
            revision_identifier=revision.revision_identifier,
            source_hash=revision.source_hash,
            total_files=revision.total_files,
            total_bytes=revision.total_bytes,
            artifacts=artifacts,
        )

    def read_artifact(
        self,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        artifact_id: UUID,
        *,
        max_bytes: int,
    ) -> bytes:
        raise AssertionError("Empty API fixtures must not request artifact content.")
