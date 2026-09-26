"""RepositoryArtifact domain entity."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.platform.ingestion.domain.constants import (
    ArtifactCategory,
    SupportLevel,
)


@dataclass(frozen=True, slots=True)
class RepositoryArtifact:
    """Domain entity representing a discovered file artifact within a revision."""

    id: UUID
    project_id: UUID
    repository_id: UUID
    revision_id: UUID
    path: str
    size_bytes: int
    content_hash: str
    category: ArtifactCategory
    support_level: SupportLevel
    storage_key: str
    created_at: datetime
