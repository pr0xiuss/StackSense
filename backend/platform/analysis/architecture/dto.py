"""Safe public DTOs for published Architecture Model queries."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ArchitectureVersionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    analysis_id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    sequence_number: int
    architecture_schema_version: str
    ir_schema_version: str
    content_digest: str
    entity_count: int
    relationship_count: int
    evidence_count: int
    unresolved_relationship_count: int
    conflict_count: int
    completeness: dict[str, Any]
    published_at: datetime


class ArchitectureEntityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    logical_id: str
    kind: str
    name: str
    namespace: tuple[str, ...]
    status: str
    evidence_ids: tuple[str, ...]
    source_ir_keys: tuple[str, ...]
    metadata: dict[str, Any]


class ArchitectureRelationshipResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    logical_id: str
    kind: str
    source_logical_id: str
    target_logical_id: str
    status: str
    evidence_ids: tuple[str, ...]
    source_ir_keys: tuple[str, ...]
    metadata: dict[str, Any]


class ArchitectureEvidenceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    logical_id: str
    source_record_type: str
    path: str
    artifact_id: UUID | None
    source_fact_key: str | None
    source_range: dict[str, Any] | None
    producer_id: str | None
    producer_version: str | None
    strength: str
    polarity: str
    metadata: dict[str, Any]


class ArchitectureUnresolvedResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    logical_id: str
    kind: str
    source_logical_id: str
    target_descriptor: str
    reason: str
    status: str
    evidence_ids: tuple[str, ...]
    candidate_references: tuple[str, ...]
    metadata: dict[str, Any]


class ArchitectureConflictResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    logical_id: str
    conflict_type: str
    subject_key: str
    evidence_ids: tuple[str, ...]
    details: dict[str, Any]


class ArchitectureCollectionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[
        ArchitectureEntityResponse
        | ArchitectureRelationshipResponse
        | ArchitectureEvidenceResponse
        | ArchitectureUnresolvedResponse
        | ArchitectureConflictResponse
    ]
    total: int
    limit: int
    offset: int


__all__ = [
    "ArchitectureCollectionResponse",
    "ArchitectureConflictResponse",
    "ArchitectureEntityResponse",
    "ArchitectureEvidenceResponse",
    "ArchitectureRelationshipResponse",
    "ArchitectureUnresolvedResponse",
    "ArchitectureVersionResponse",
]
