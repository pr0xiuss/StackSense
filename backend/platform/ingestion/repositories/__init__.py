"""Ingestion persistence contracts."""

from backend.platform.ingestion.repositories.artifact_repo import (
    ArtifactRepository,
)
from backend.platform.ingestion.repositories.ingestion_repo import (
    IngestionRepository,
)
from backend.platform.ingestion.repositories.revision_repo import (
    RevisionRepository,
)

__all__ = [
    "ArtifactRepository",
    "IngestionRepository",
    "RevisionRepository",
]
