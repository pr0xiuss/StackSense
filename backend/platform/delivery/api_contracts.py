"""P5 delivery API candidate: safe metadata, no leases or producer payloads."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.platform.delivery.contracts import (
    ArtifactReference,
    DiagramTemplate,
    FrozenContract,
    VersionScope,
    WorkKind,
)


class DeliveryApiError(Exception):
    def __init__(self, code: str, status: int = 409) -> None:
        self.code, self.status = code, status
        super().__init__(code)


class ManualRetryPolicy(FrozenContract):
    """Explicit approved operational policy; no test values become defaults."""

    max_rounds: Annotated[int, Field(gt=0)]
    window_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    max_actor_requests: Annotated[int, Field(gt=0)]
    max_project_requests: Annotated[int, Field(gt=0)]


class RetryRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )
    resource_type: WorkKind
    resource_id: UUID
    idempotency_key: Annotated[
        str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    ]


class RetryAccepted(FrozenContract):
    scope: VersionScope
    operation_id: UUID
    work_id: UUID
    retry_of_work_id: UUID
    state: Literal["PENDING"] = "PENDING"


DeliveryState = Literal[
    "PENDING",
    "QUEUED",
    "RUNNING",
    "RETRYING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "WAITING_FOR_DIAGRAMS",
]
DeliveryEligibility = Literal[
    "WAITING_FOR_ANALYSIS", "ELIGIBLE", "INELIGIBLE", "NOT_SCHEDULED"
]


class WorkSummary(FrozenContract):
    kind: WorkKind
    template: DiagramTemplate | Literal["architecture_analysis"] | None = None
    work_id: UUID | None = None
    state: DeliveryState
    reason: str | None = None
    run_number: int = 0
    executions: int = 0
    max_executions: int | None = None
    retry_allowed: bool = False
    reference: ArtifactReference | None = None
    cancellation_cause: str | None = None


class DeliverySummary(FrozenContract):
    scope: VersionScope
    bundle_id: UUID | None = None
    policy_version: str | None = None
    eligibility: DeliveryEligibility
    diagrams: tuple[WorkSummary, ...] = ()
    search: WorkSummary | None = None
    report: WorkSummary | None = None
    waiting_on: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    sibling_release_reason: str | None = None
    updated_at: datetime | None = None
    last_reconciler_at: datetime | None = None
    source_error: str | None = None


class DeliveryError(BaseModel):
    code: str
    message: str
    details: dict[str, object]


class DeliveryErrorResponse(BaseModel):
    error: DeliveryError
