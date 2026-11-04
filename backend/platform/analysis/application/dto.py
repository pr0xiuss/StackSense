"""Lifecycle request and response Data Transfer Objects."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateAnalysisRequest:
    """Request DTO to initiate a new analysis run."""

    project_id: UUID
    repository_id: UUID
    revision_id: UUID
    include_paths: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = ()
    max_file_size_bytes: int = 5 * 1024 * 1024
    timeout_seconds: int = 1800
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class CancelAnalysisRequest:
    """Request DTO to cancel an active analysis run."""

    reason: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisJobResponse:
    """Response DTO for background Job execution state."""

    id: UUID
    analysis_id: UUID
    status: str
    attempt: int
    max_attempts: int
    version: int
    created_at: datetime
    updated_at: datetime
    worker_id: str | None = None
    heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisStageResponse:
    """Response DTO for stage execution state."""

    id: UUID
    analysis_id: UUID
    stage_name: str
    status: str
    order: int
    is_mandatory: bool
    processed_items: int
    total_items: int
    version: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisEventResponse:
    """Response DTO for durable lifecycle events."""

    id: UUID
    analysis_id: UUID
    sequence_number: int
    event_type: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AnalysisDiagnosticResponse:
    """Response DTO for diagnostic findings."""

    id: UUID
    analysis_id: UUID
    code: str
    category: str
    severity: str
    scope: str
    message: str
    retryability: str
    created_at: datetime
    stage: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    artifact_id: UUID | None = None
    artifact_path: str | None = None
    source_line: int | None = None
    source_column: int | None = None


@dataclass(frozen=True, slots=True)
class AnalysisCompletenessResponse:
    """Response DTO for analysis coverage and completeness details."""

    analyzed_files_count: int
    unsupported_files_count: int
    failed_files_count: int
    excluded_files_count: int
    is_partial: bool
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AnalysisResponse:
    """Full lifecycle response representation of an Analysis."""

    id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    status: str
    configuration: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    completeness: AnalysisCompletenessResponse | None = None
    published_version_id: UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    stages: list[AnalysisStageResponse] = field(default_factory=list)
    active_job: AnalysisJobResponse | None = None


@dataclass(frozen=True, slots=True)
class AnalysisListResponse:
    """Paginated collection of analyses."""

    items: list[AnalysisResponse]
    total: int
    limit: int
    offset: int
