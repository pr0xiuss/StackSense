"""M5 internal read DTOs and API contracts.

These closed models define the metadata, collection, history, download,
retry, and sanitized error response payloads for the Architecture Analysis Report.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from backend.platform.delivery.contracts import VersionScope
from backend.platform.reports.contracts import (
    FrozenReportModel,
    ReportCollection,
    ReportGenerationPage,
    ReportGenerationSummary,
    ReportSlotStatus,
    ReportSummary,
)


class ReportErrorDetails(FrozenReportModel):
    """Sanitized details for client error envelopes."""

    dimension: str | None = None
    actual: int | None = None
    limit: int | None = None
    request_id: UUID | None = None


class ReportErrorBody(FrozenReportModel):
    """Sanitized report error body."""

    code: str
    message: str
    details: ReportErrorDetails = Field(default_factory=ReportErrorDetails)


class ErrorResponse(FrozenReportModel):
    """Standard client error response for report operations."""

    error: ReportErrorBody


class ReportRetryRequest(FrozenReportModel):
    """Request payload for retrying a failed report generation."""

    idempotency_key: Annotated[
        str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    ]


class ReportRetryResponse(FrozenReportModel):
    """Accepted response for report retry."""

    scope: VersionScope
    report_id: UUID
    work_id: UUID
    operation_id: UUID
    state: Literal["PENDING"] = "PENDING"


__all__ = [
    "ErrorResponse",
    "ReportCollection",
    "ReportErrorBody",
    "ReportErrorDetails",
    "ReportGenerationPage",
    "ReportGenerationSummary",
    "ReportRetryRequest",
    "ReportRetryResponse",
    "ReportSlotStatus",
    "ReportSummary",
]
