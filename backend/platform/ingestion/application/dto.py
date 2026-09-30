"""Application DTOs for Ingestion, Revision, and Artifact."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.platform.errors import InvalidGitHubUrlError, SourceValidationError
from backend.platform.ingestion.domain.constants import SourceType
from backend.platform.ingestion.domain.source import (
    normalize_source_type,
    validate_github_ref,
    validate_github_url,
)


class TriggerIngestionRequest(BaseModel):
    """Request payload to trigger repository ingestion.

    Supports three source acquisition modes:
    1. Public GitHub repository ('github')
    2. Source archive ('archive', legacy 'zip')
    3. Server path ('server_path', legacy 'directory')
    """

    model_config = ConfigDict(frozen=True)

    repository_id: UUID | None = Field(
        default=None,
        description="Target repository ID (optional if passed in route parameter)",
    )
    source_type: SourceType = Field(
        default=SourceType.ARCHIVE,
        description="Type of source: 'github', 'archive', or 'server_path'",
    )
    source_reference: str | None = Field(
        default=None,
        description="Local staging path, server path, or provenance reference",
        max_length=1024,
    )
    repository_url: str | None = Field(
        default=None,
        description="Public GitHub repository URL (required for github source)",
        max_length=1024,
    )
    ref: str | None = Field(
        default=None,
        description="Optional Git branch, tag, or commit reference for GitHub",
        max_length=255,
    )
    revision_identifier: str | None = Field(
        default=None,
        description="Optional explicit revision identifier (tag, branch, commit)",
        max_length=255,
    )

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize_payload(cls, data: Any) -> Any:
        """Validate and normalize source parameters at input boundary."""
        if not isinstance(data, dict):
            return data

        mutable_data = dict(data)

        # 1. Normalize source_type
        # Unknown source types are rejected with InvalidSourceTypeError
        raw_source_type = mutable_data.get("source_type", SourceType.ARCHIVE)
        norm_source_type = normalize_source_type(raw_source_type)
        mutable_data["source_type"] = norm_source_type

        # 2. Source-specific validation
        if norm_source_type == SourceType.GITHUB:
            raw_url = mutable_data.get("repository_url") or mutable_data.get(
                "source_reference"
            )
            if not raw_url or not str(raw_url).strip():
                raise InvalidGitHubUrlError(
                    "GitHub ingestion requires 'repository_url'."
                )
            normalized_url = validate_github_url(str(raw_url))
            validated_ref = validate_github_ref(mutable_data.get("ref"))

            mutable_data["repository_url"] = normalized_url
            mutable_data["ref"] = validated_ref
            mutable_data["source_reference"] = (
                f"{normalized_url}@{validated_ref}" if validated_ref else normalized_url
            )

        elif norm_source_type in (SourceType.ARCHIVE, SourceType.SERVER_PATH):
            raw_ref = mutable_data.get("source_reference")
            if not raw_ref or not str(raw_ref).strip():
                mode_name = (
                    "Archive"
                    if norm_source_type == SourceType.ARCHIVE
                    else "Server path"
                )
                raise SourceValidationError(
                    f"{mode_name} ingestion requires a non-empty 'source_reference'."
                )
            mutable_data["source_reference"] = str(raw_ref).strip()

        # 3. Clean optional revision_identifier
        if mutable_data.get("revision_identifier") is not None:
            clean_rev = str(mutable_data["revision_identifier"]).strip()
            mutable_data["revision_identifier"] = clean_rev if clean_rev else None

        return mutable_data


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
