"""Domain records and frozen M1 contracts for graph projection lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from backend.platform.graph.neo4j import GRAPH_SCHEMA_VERSION

PROJECTION_TYPE: Final = "architecture"
PROJECTION_CONTRACT_VERSION: Final = "1.0.0"
SOURCE_CONTRACT_VERSION: Final = "1.0.0"
WORKER_CONTRACT_VERSION: Final = "1.0.0"
PROJECTOR_VERSION: Final = "1.0.0"
MAX_EXECUTIONS: Final = 3


class ProjectionPublicState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STALE = "STALE"


class ProjectionAttemptState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class ProjectionActorType(StrEnum):
    SYSTEM = "SYSTEM"
    USER = "USER"


class ActivationDisposition(StrEnum):
    ACTIVATED = "activated"
    ALREADY_ACTIVATED = "already_activated"
    REJECTED_STALE = "rejected_stale"
    RECORDED_FAILURE = "recorded_failure"


@dataclass(frozen=True, slots=True)
class ProjectionCounts:
    entities: int
    relationships: int
    evidence: int
    unresolved: int
    conflicts: int

    def __post_init__(self) -> None:
        if (
            min(
                self.entities,
                self.relationships,
                self.evidence,
                self.unresolved,
                self.conflicts,
            )
            < 0
        ):
            raise ValueError("projection counts must be non-negative")


@dataclass(frozen=True, slots=True)
class ProjectionResource:
    id: UUID
    architecture_version_id: UUID
    project_id: UUID
    repository_id: UUID
    architecture_sequence: int
    projection_type: str
    source_content_digest: str
    source_schema_version: str
    state: ProjectionPublicState
    active_generation_id: UUID | None
    active_projector_version: str | None
    active_graph_schema_version: str | None
    active_payload_digest: str | None
    active_counts: ProjectionCounts | None
    last_failure_code: str | None
    last_failure_message: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProjectionAttempt:
    id: UUID
    resource_id: UUID
    generation_id: UUID
    attempt_number: int
    state: ProjectionAttemptState
    actor_type: ProjectionActorType
    actor_id: UUID | None
    actor_role: str | None
    correlation_id: str
    contract_version: str
    source_content_digest: str
    source_schema_version: str
    graph_schema_version: str
    projector_version: str
    execution_count: int
    dispatch_count: int
    dispatched_at: datetime | None
    lease_owner: str | None
    lease_token: str | None
    lease_heartbeat_at: datetime | None
    lease_expires_at: datetime | None
    expected_counts: ProjectionCounts
    actual_counts: ProjectionCounts | None
    expected_key_set_digest: str | None
    actual_key_set_digest: str | None
    expected_endpoint_digest: str | None
    actual_endpoint_digest: str | None
    expected_payload_digest: str | None
    actual_payload_digest: str | None
    failure_code: str | None
    failure_message: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProjectionLease:
    resource_id: UUID
    attempt_id: UUID
    generation_id: UUID
    worker_id: str
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectionWorkClaim:
    """Validated immutable identity carried by one P4-W1 delivery."""

    projection_id: UUID
    attempt_id: UUID
    project_id: UUID
    architecture_version_id: UUID
    generation_id: UUID
    contract_version: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class VerificationReceipt:
    """M1-required envelope returned by the future M2 verifier."""

    resource_id: UUID
    attempt_id: UUID
    generation_id: UUID
    project_id: UUID
    architecture_version_id: UUID
    lease_owner: str
    lease_token: str
    contract_version: str
    source_content_digest: str
    source_schema_version: str
    graph_schema_version: str
    projector_version: str
    verified: bool
    expected_counts: ProjectionCounts
    actual_counts: ProjectionCounts | None
    expected_key_set_digest: str | None
    actual_key_set_digest: str | None
    expected_endpoint_digest: str | None
    actual_endpoint_digest: str | None
    expected_payload_digest: str | None
    actual_payload_digest: str | None
    failure_code: str | None = None
    failure_message: str | None = None

    def summaries_match(self) -> bool:
        if not self.verified or self.actual_counts != self.expected_counts:
            return False
        pairs = (
            (self.expected_key_set_digest, self.actual_key_set_digest),
            (self.expected_endpoint_digest, self.actual_endpoint_digest),
            (self.expected_payload_digest, self.actual_payload_digest),
        )
        return all(
            expected is not None and expected == actual for expected, actual in pairs
        )


@dataclass(frozen=True, slots=True)
class ActivationResult:
    disposition: ActivationDisposition
    resource: ProjectionResource
    attempt: ProjectionAttempt


def utc_now() -> datetime:
    return datetime.now(UTC)


ACTIVE_ATTEMPT_STATES: Final = frozenset(
    {
        ProjectionAttemptState.QUEUED,
        ProjectionAttemptState.RUNNING,
        ProjectionAttemptState.RETRYING,
    }
)

__all__ = [
    "ACTIVE_ATTEMPT_STATES",
    "ActivationDisposition",
    "ActivationResult",
    "GRAPH_SCHEMA_VERSION",
    "MAX_EXECUTIONS",
    "PROJECTOR_VERSION",
    "PROJECTION_CONTRACT_VERSION",
    "PROJECTION_TYPE",
    "ProjectionActorType",
    "ProjectionAttempt",
    "ProjectionAttemptState",
    "ProjectionCounts",
    "ProjectionLease",
    "ProjectionPublicState",
    "ProjectionResource",
    "ProjectionWorkClaim",
    "SOURCE_CONTRACT_VERSION",
    "VerificationReceipt",
    "WORKER_CONTRACT_VERSION",
]
