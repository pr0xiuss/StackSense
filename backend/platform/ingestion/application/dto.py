"""Application DTOs for Ingestion, Revision, and Artifact."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TriggerIngestionRequest(BaseModel):
    """Request payload to trigger repository ingestion.

    Note: In Phase 2 MVP, source_reference represents a verified local path or
    staged file reference on disk. Upload endpoints bridge remote multipart
    payloads into temporary local staging paths before invocation.
    """

    model_config = ConfigDict(frozen=True)

    repository_id: UUID
    source_type: str = Field(
        default="archive",
        description="Type of source ('archive' or 'directory')",
    )
    source_reference: str = Field(
        ...,
        description="Local staging path or URI to the source archive or directory",
        min_length=1,
        max_length=1024,
    )
    revision_identifier: str | None = Field(
        default=None,
        description="Optional explicit revision identifier (tag, branch, commit)",
        max_length=255,
    )


class IngestionResponse(BaseModel):
    """Response DTO for an Ingestion job."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    repository_id: UUID
    source_type: str
    source_reference: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RevisionResponse(BaseModel):
    """Response DTO for a captured RepositoryRevision."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    repository_id: UUID
    ingestion_id: UUID | None = None
    revision_identifier: str
    source_hash: str
    total_files: int
    total_bytes: int
    created_at: datetime


class ArtifactResponse(BaseModel):
    """Response DTO for a discovered RepositoryArtifact."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    repository_id: UUID
    revision_id: UUID
    path: str
    size_bytes: int
    content_hash: str
    category: str
    support_level: str
    storage_key: str
    created_at: datetime
