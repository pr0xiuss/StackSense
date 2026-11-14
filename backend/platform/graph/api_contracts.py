"""P4-D1 graph API contracts, DTOs, and error classes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.platform.graph.model import ProjectionCounts

P4_D1_CONTRACT_VERSION: Final[str] = "1.0.0"


class ProjectionAttemptSummary(BaseModel):
    """Safe public summary of an active projection attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_id: UUID
    attempt_number: int
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class ProjectionStatusResponse(BaseModel):
    """Public status response for a projected architecture graph resource."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_id: UUID
    project_id: UUID
    architecture_version_id: UUID
    projection_type: str
    status: str
    active_generation_id: UUID | None = None
    schema_version: str | None = None
    projector_version: str | None = None
    counts: ProjectionCounts | None = None
    last_failure_code: str | None = None
    created_at: datetime
    updated_at: datetime
    last_attempt_at: datetime | None = None
    active_attempt: ProjectionAttemptSummary | None = None


class ProjectionRebuildAcceptedResponse(BaseModel):
    """Response returned when a rebuild mutation is durably accepted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_id: UUID
    architecture_version_id: UUID
    status: str
    attempt_id: UUID
    attempt_number: int
    attempt_status: str
    accepted_at: datetime


class GraphErrorBody(BaseModel):
    """Canonical error payload schema matching StackSense error envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class GraphErrorResponse(BaseModel):
    """OpenAPI schema for safe graph error responses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    error: GraphErrorBody


class GraphApiError(Exception):
    """Base exception for safe M4 graph API failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.safe_details = dict(safe_details) if safe_details else {}


class GraphRebuildConflictError(GraphApiError):
    """Raised when an active rebuild attempt cannot be composed."""

    def __init__(
        self,
        message: str = "Graph projection rebuild conflict",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_rebuild_conflict",
            safe_details=safe_details,
        )


class GraphLifecycleUnavailableError(GraphApiError):
    """Raised when PostgreSQL lifecycle persistence or transaction commit fails."""

    def __init__(
        self,
        message: str = "Graph lifecycle service is unavailable",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_lifecycle_unavailable",
            safe_details=safe_details,
        )


class GraphApiInternalError(GraphApiError):
    """Raised when an unexpected internal error occurs within the graph API layer."""

    def __init__(
        self,
        message: str = "Internal graph API error",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_api_internal_error",
            safe_details=safe_details,
        )
