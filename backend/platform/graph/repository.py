"""Persistence port for the P4 graph projection control plane."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from backend.platform.graph.model import (
    ActivationResult,
    ProjectionActorType,
    ProjectionAttempt,
    ProjectionLease,
    ProjectionResource,
    ProjectionWorkClaim,
    VerificationReceipt,
)
from backend.platform.graph.source import PublishedArchitectureHeader


class GraphLifecycleError(RuntimeError):
    """Base safe lifecycle failure."""


class GraphLifecycleIntegrityError(GraphLifecycleError):
    """Raised when immutable scope or persisted state is inconsistent."""


class GraphLifecycleStateError(GraphLifecycleError):
    """Raised when an operation is invalid for the current lifecycle state."""


@dataclass(frozen=True, slots=True)
class EnsureProjectionResult:
    resource: ProjectionResource
    attempt: ProjectionAttempt | None
    created: bool


@dataclass(frozen=True, slots=True)
class DispatchCandidate:
    resource: ProjectionResource
    attempt: ProjectionAttempt


class GraphProjectionRepository(ABC):
    """Caller-owned unit-of-work port for projection lifecycle state."""

    @abstractmethod
    def ensure_with_initial_attempt(
        self,
        header: PublishedArchitectureHeader,
        *,
        correlation_id: str,
    ) -> EnsureProjectionResult: ...

    @abstractmethod
    def create_rebuild_attempt(
        self,
        resource_id: UUID,
        *,
        actor_type: ProjectionActorType,
        actor_id: UUID | None,
        actor_role: str | None,
        correlation_id: str,
    ) -> ProjectionAttempt: ...

    @abstractmethod
    def get_resource(self, resource_id: UUID) -> ProjectionResource | None: ...

    @abstractmethod
    def get_attempt(self, attempt_id: UUID) -> ProjectionAttempt | None: ...

    @abstractmethod
    def mark_dispatched(
        self, attempt_id: UUID, *, at: datetime
    ) -> ProjectionAttempt: ...

    @abstractmethod
    def list_dispatch_candidates(
        self,
        *,
        now: datetime,
        dispatched_before: datetime,
        retry_ready_before: datetime,
        limit: int,
    ) -> tuple[DispatchCandidate, ...]: ...

    @abstractmethod
    def list_expired_attempt_ids(
        self, *, now: datetime, limit: int
    ) -> tuple[UUID, ...]: ...

    @abstractmethod
    def acquire_lease(
        self,
        claim: ProjectionWorkClaim,
        *,
        worker_id: str,
        now: datetime,
        duration: timedelta,
    ) -> ProjectionLease | None: ...

    @abstractmethod
    def heartbeat(
        self,
        lease: ProjectionLease,
        *,
        now: datetime,
        duration: timedelta,
    ) -> ProjectionLease | None: ...

    @abstractmethod
    def record_execution_failure(
        self,
        lease: ProjectionLease,
        *,
        now: datetime,
        failure_code: str,
        failure_message: str,
        transient: bool,
    ) -> ProjectionAttempt: ...

    @abstractmethod
    def recover_expired_attempt(
        self,
        attempt_id: UUID,
        *,
        now: datetime,
    ) -> ProjectionAttempt | None: ...

    @abstractmethod
    def activate_verified(
        self,
        receipt: VerificationReceipt,
        *,
        now: datetime,
    ) -> ActivationResult: ...

    @abstractmethod
    def mark_older_resources_stale(
        self, header: PublishedArchitectureHeader, *, now: datetime
    ) -> int: ...


__all__ = [
    "DispatchCandidate",
    "EnsureProjectionResult",
    "GraphLifecycleError",
    "GraphLifecycleIntegrityError",
    "GraphLifecycleStateError",
    "GraphProjectionRepository",
]
