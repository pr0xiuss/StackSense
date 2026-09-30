"""RepositoryRevision domain entity."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RepositoryRevision:
    """Domain entity representing a specific captured source revision."""

    id: UUID
    project_id: UUID
    repository_id: UUID
    ingestion_id: UUID | None
    revision_identifier: str
    source_hash: str
    total_files: int
    total_bytes: int
    created_at: datetime
