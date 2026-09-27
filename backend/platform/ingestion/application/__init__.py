"""Ingestion application layer."""

from backend.platform.ingestion.application.acquisition import (
    AcquisitionHandler,
    AcquisitionResult,
)
from backend.platform.ingestion.application.classifier import (
    ArtifactClassifier,
)
from backend.platform.ingestion.application.dto import (
    ArtifactResponse,
    IngestionResponse,
    RevisionResponse,
    TriggerIngestionRequest,
)
from backend.platform.ingestion.application.service import (
    DefaultIngestionService,
    IngestionService,
)
from backend.platform.ingestion.application.storage import StorageService
from backend.platform.ingestion.application.validator import (
    DiscoveredFile,
    SourceValidator,
    ValidatedSource,
)

__all__ = [
    "AcquisitionHandler",
    "AcquisitionResult",
    "ArtifactClassifier",
    "ArtifactResponse",
    "DefaultIngestionService",
    "DiscoveredFile",
    "IngestionResponse",
    "IngestionService",
    "RevisionResponse",
    "SourceValidator",
    "StorageService",
    "TriggerIngestionRequest",
    "ValidatedSource",
]
