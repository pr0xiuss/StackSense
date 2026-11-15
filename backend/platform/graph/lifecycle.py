"""Application service for M1 projection lifecycle and activation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from backend.platform.graph.model import (
    WORKER_CONTRACT_VERSION,
    ActivationResult,
    ProjectionActorType,
    ProjectionAttempt,
    ProjectionAttemptState,
    ProjectionLease,
    VerificationReceipt,
)
from backend.platform.graph.queue import ProjectionPublisher, ProjectionWorkPayload
from backend.platform.graph.repository import (
    EnsureProjectionResult,
    GraphProjectionRepository,
)
from backend.platform.graph.source import (
    PublishedArchitectureHeader,
    PublishedArchitectureSource,
)


@dataclass(frozen=True, slots=True)
class ReconciliationDecision:
    result: EnsureProjectionResult
    work: ProjectionWorkPayload | None
    stale_resources: int


@dataclass(frozen=True, slots=True)
class ReconciliationSummary:
    publications_scanned: int = 0
    resources_created: int = 0
    stale_resources: int = 0
    expired_leases_recovered: int = 0
    terminal_expired_attempts: int = 0
    dispatch_candidates: int = 0
    dispatched: int = 0
    publish_failures: int = 0
    dispatch_enabled: bool = False


class GraphProjectionLifecycle:
    """Coordinates lifecycle rules without owning transaction commits."""

    def __init__(self, repository: GraphProjectionRepository) -> None:
        self._repository = repository

    def reconcile_published(
        self,
        header: PublishedArchitectureHeader,
        *,
        correlation_id: str,
        now: datetime | None = None,
    ) -> ReconciliationDecision:
        at = now or datetime.now(UTC)
        stale = self._repository.mark_older_resources_stale(header, now=at)
        result = self._repository.ensure_with_initial_attempt(
            header,
            correlation_id=correlation_id,
        )
        work = None
        if result.created and result.attempt is not None:
            work = self._payload(result, result.attempt)
        return ReconciliationDecision(result=result, work=work, stale_resources=stale)

    def request_rebuild(
        self,
        resource_id: UUID,
        *,
        actor_id: UUID,
        actor_role: str,
        correlation_id: str,
    ) -> tuple[ProjectionAttempt, ProjectionWorkPayload]:
        attempt = self._repository.create_rebuild_attempt(
            resource_id,
            actor_type=ProjectionActorType.USER,
            actor_id=actor_id,
            actor_role=actor_role,
            correlation_id=correlation_id,
        )
        resource = self._repository.get_resource(resource_id)
        if resource is None:
            raise RuntimeError("projection resource disappeared during rebuild")
        return attempt, ProjectionWorkPayload(
            projection_id=resource.id,
            attempt_id=attempt.id,
            project_id=resource.project_id,
            architecture_version_id=resource.architecture_version_id,
            generation_id=attempt.generation_id,
            contract_version=WORKER_CONTRACT_VERSION,
            correlation_id=attempt.correlation_id,
        )

    def acquire(
        self,
        payload: ProjectionWorkPayload,
        *,
        worker_id: str,
        lease_duration: timedelta,
        now: datetime | None = None,
    ) -> ProjectionLease | None:
        return self._repository.acquire_lease(
            payload.to_claim(),
            worker_id=worker_id,
            now=now or datetime.now(UTC),
            duration=lease_duration,
        )

    def heartbeat(
        self,
        lease: ProjectionLease,
        *,
        lease_duration: timedelta,
        now: datetime | None = None,
    ) -> ProjectionLease | None:
        return self._repository.heartbeat(
            lease,
            now=now or datetime.now(UTC),
            duration=lease_duration,
        )

    def record_failure(
        self,
        lease: ProjectionLease,
        *,
        failure_code: str,
        failure_message: str,
        transient: bool,
        now: datetime | None = None,
    ) -> ProjectionAttempt:
        return self._repository.record_execution_failure(
            lease,
            now=now or datetime.now(UTC),
            failure_code=failure_code,
            failure_message=failure_message,
            transient=transient,
        )

    def recover_expired(
        self,
        attempt_id: UUID,
        *,
        now: datetime | None = None,
    ) -> ProjectionAttempt | None:
        """Invalidate an expired worker lease while retaining its generation."""
        return self._repository.recover_expired_attempt(
            attempt_id,
            now=now or datetime.now(UTC),
        )

    def activate(
        self,
        receipt: VerificationReceipt,
        *,
        now: datetime | None = None,
    ) -> ActivationResult:
        return self._repository.activate_verified(
            receipt,
            now=now or datetime.now(UTC),
        )

    @staticmethod
    def payload_for(
        resource_id: UUID,
        repository: GraphProjectionRepository,
        attempt: ProjectionAttempt,
    ) -> ProjectionWorkPayload:
        resource = repository.get_resource(resource_id)
        if resource is None or resource.id != attempt.resource_id:
            raise RuntimeError("projection dispatch scope is inconsistent")
        return ProjectionWorkPayload(
            projection_id=resource.id,
            attempt_id=attempt.id,
            project_id=resource.project_id,
            architecture_version_id=resource.architecture_version_id,
            generation_id=attempt.generation_id,
            contract_version=WORKER_CONTRACT_VERSION,
            correlation_id=attempt.correlation_id,
        )

    @staticmethod
    def _payload(
        result: EnsureProjectionResult, attempt: ProjectionAttempt
    ) -> ProjectionWorkPayload:
        resource = result.resource
        return ProjectionWorkPayload(
            projection_id=resource.id,
            attempt_id=attempt.id,
            project_id=resource.project_id,
            architecture_version_id=resource.architecture_version_id,
            generation_id=attempt.generation_id,
            contract_version=WORKER_CONTRACT_VERSION,
            correlation_id=attempt.correlation_id,
        )


class GraphProjectionReconciler:
    """Discover publications and recover durable work without owning projection."""

    def __init__(
        self,
        *,
        source: PublishedArchitectureSource,
        repository: GraphProjectionRepository,
        publisher: ProjectionPublisher,
        checkpoint: Callable[[], None],
        rollback: Callable[[], None],
        execution_ready: Callable[[], bool],
        page_size: int,
        recovery_batch_size: int,
        dispatch_recovery_after: timedelta,
        retry_backoff: timedelta,
    ) -> None:
        if not 1 <= page_size <= 500 or not 1 <= recovery_batch_size <= 500:
            raise ValueError("graph reconciliation limits must be 1..500")
        if dispatch_recovery_after <= timedelta(0) or retry_backoff <= timedelta(0):
            raise ValueError("graph recovery durations must be positive")
        self._source = source
        self._repository = repository
        self._publisher = publisher
        self._checkpoint = checkpoint
        self._rollback = rollback
        self._execution_ready = execution_ready
        self._page_size = page_size
        self._recovery_batch_size = recovery_batch_size
        self._dispatch_recovery_after = dispatch_recovery_after
        self._retry_backoff = retry_backoff

    def reconcile(
        self, *, correlation_id: str, now: datetime | None = None
    ) -> ReconciliationSummary:
        at = now or datetime.now(UTC)
        lifecycle = GraphProjectionLifecycle(self._repository)
        scanned = created = stale = 0
        cursor = None
        while True:
            page = self._source.list_published(limit=self._page_size, after=cursor)
            for header in page.items:
                decision = lifecycle.reconcile_published(
                    header,
                    correlation_id=f"{correlation_id}:{header.architecture_version_id}",
                    now=at,
                )
                self._checkpoint()
                scanned += 1
                created += int(decision.result.created)
                stale += decision.stale_resources
            if page.next_cursor is None:
                break
            cursor = page.next_cursor

        recovered = terminal = 0
        for attempt_id in self._repository.list_expired_attempt_ids(
            now=at, limit=self._recovery_batch_size
        ):
            attempt = lifecycle.recover_expired(attempt_id, now=at)
            if attempt is None:
                continue
            self._checkpoint()
            if attempt.state is ProjectionAttemptState.RETRYING:
                recovered += 1
            else:
                terminal += 1

        enabled = self._execution_ready()
        candidates = self._repository.list_dispatch_candidates(
            now=at,
            dispatched_before=at - self._dispatch_recovery_after,
            retry_ready_before=at - self._retry_backoff,
            limit=self._recovery_batch_size,
        )
        if not enabled:
            return ReconciliationSummary(
                publications_scanned=scanned,
                resources_created=created,
                stale_resources=stale,
                expired_leases_recovered=recovered,
                terminal_expired_attempts=terminal,
                dispatch_candidates=len(candidates),
                dispatch_enabled=False,
            )

        dispatched = failures = 0
        for candidate in candidates:
            payload = GraphProjectionLifecycle.payload_for(
                candidate.resource.id, self._repository, candidate.attempt
            )
            try:
                self._publisher.publish(payload)
            except Exception:
                self._rollback()
                failures += 1
                continue
            self._repository.mark_dispatched(candidate.attempt.id, at=at)
            self._checkpoint()
            dispatched += 1

        return ReconciliationSummary(
            publications_scanned=scanned,
            resources_created=created,
            stale_resources=stale,
            expired_leases_recovered=recovered,
            terminal_expired_attempts=terminal,
            dispatch_candidates=len(candidates),
            dispatched=dispatched,
            publish_failures=failures,
            dispatch_enabled=True,
        )


__all__ = [
    "GraphProjectionLifecycle",
    "GraphProjectionReconciler",
    "ReconciliationDecision",
    "ReconciliationSummary",
]
