"""Projection lifecycle, lease, retry, rebuild, and activation tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.platform.graph.lifecycle import GraphProjectionLifecycle
from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTION_CONTRACT_VERSION,
    PROJECTOR_VERSION,
    ActivationDisposition,
    ProjectionAttemptState,
    ProjectionCounts,
    ProjectionPublicState,
    VerificationReceipt,
)
from backend.platform.graph.persistence import (
    GraphProjectionAttemptModel,
    SqlAlchemyGraphProjectionRepository,
)
from backend.platform.graph.repository import (
    GraphLifecycleIntegrityError,
    GraphLifecycleStateError,
)
from backend.platform.graph.source import PublishedArchitectureHeader
from backend.platform.projects.infra.base import Base


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value
    engine.dispose()


def _header(
    *,
    repository_id: UUID | None = None,
    sequence: int = 1,
) -> PublishedArchitectureHeader:
    return PublishedArchitectureHeader(
        contract_version="1.0.0",
        architecture_version_id=uuid4(),
        analysis_id=uuid4(),
        project_id=uuid4(),
        repository_id=repository_id or uuid4(),
        snapshot_id=uuid4(),
        sequence_number=sequence,
        published_at=datetime.now(UTC),
        configuration_fingerprint="configuration",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        content_digest=f"source-{sequence}",
        counts=ProjectionCounts(2, 1, 3, 1, 0),
    )


def _successful_receipt(
    *,
    header: PublishedArchitectureHeader,
    resource_id: UUID,
    attempt_id: UUID,
    generation_id: UUID,
    lease_owner: str,
    lease_token: str,
) -> VerificationReceipt:
    return VerificationReceipt(
        resource_id=resource_id,
        attempt_id=attempt_id,
        generation_id=generation_id,
        project_id=header.project_id,
        architecture_version_id=header.architecture_version_id,
        lease_owner=lease_owner,
        lease_token=lease_token,
        contract_version=PROJECTION_CONTRACT_VERSION,
        source_content_digest=header.content_digest,
        source_schema_version=header.architecture_schema_version,
        graph_schema_version=GRAPH_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        verified=True,
        expected_counts=header.counts,
        actual_counts=header.counts,
        expected_key_set_digest="keys",
        actual_key_set_digest="keys",
        expected_endpoint_digest="endpoints",
        actual_endpoint_digest="endpoints",
        expected_payload_digest="payload",
        actual_payload_digest="payload",
    )


def _work_payload(repository, attempt):
    return GraphProjectionLifecycle.payload_for(
        attempt.resource_id, repository, attempt
    )


def _activate(
    lifecycle: GraphProjectionLifecycle,
    repository: SqlAlchemyGraphProjectionRepository,
    header: PublishedArchitectureHeader,
    resource_id: UUID,
    attempt_id: UUID,
    generation_id: UUID,
) -> None:
    now = datetime.now(UTC)
    lease = lifecycle.acquire(
        _work_payload(repository, repository.get_attempt(attempt_id)),
        worker_id="worker-1",
        lease_duration=timedelta(minutes=5),
        now=now,
    )
    assert lease is not None
    result = lifecycle.activate(
        _successful_receipt(
            header=header,
            resource_id=resource_id,
            attempt_id=attempt_id,
            generation_id=generation_id,
            lease_owner=lease.worker_id,
            lease_token=lease.token,
        ),
        now=now + timedelta(seconds=1),
    )
    assert result.disposition is ActivationDisposition.ACTIVATED


def test_reconciliation_is_idempotent_and_does_not_backfill_attempts(
    session: Session,
) -> None:
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    header = _header()

    first = lifecycle.reconcile_published(header, correlation_id="first")
    second = lifecycle.reconcile_published(header, correlation_id="second")

    assert first.result.created and first.work is not None
    assert not second.result.created and second.work is None
    assert second.result.attempt is not None
    assert second.result.attempt.id == first.result.attempt.id  # type: ignore[union-attr]
    assert (
        session.scalar(select(func.count()).select_from(GraphProjectionAttemptModel))
        == 1
    )


def test_lease_is_exclusive_and_heartbeat_rejects_old_token(session: Session) -> None:
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    decision = lifecycle.reconcile_published(_header(), correlation_id="lease")
    attempt = decision.result.attempt
    assert attempt is not None
    now = datetime.now(UTC)
    lease = lifecycle.acquire(
        _work_payload(repository, attempt),
        worker_id="worker-1",
        lease_duration=timedelta(seconds=30),
        now=now,
    )
    assert lease is not None
    assert (
        lifecycle.acquire(
            _work_payload(repository, attempt),
            worker_id="worker-2",
            lease_duration=timedelta(seconds=30),
            now=now,
        )
        is None
    )
    assert (
        lifecycle.heartbeat(
            lease,
            lease_duration=timedelta(seconds=30),
            now=now + timedelta(seconds=31),
        )
        is None
    )


@pytest.mark.parametrize(
    "field",
    (
        "projection_id",
        "attempt_id",
        "project_id",
        "architecture_version_id",
        "generation_id",
        "contract_version",
        "correlation_id",
    ),
)
def test_lease_rejects_worker_scope_mismatch_without_consuming_execution(
    session: Session, field: str
) -> None:
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    decision = lifecycle.reconcile_published(_header(), correlation_id="scope")
    attempt = decision.result.attempt
    assert attempt is not None and decision.work is not None
    if field == "contract_version":
        invalid_value = "2.0.0"
    elif field == "correlation_id":
        invalid_value = "different-correlation"
    else:
        invalid_value = uuid4()
    invalid = decision.work.model_copy(update={field: invalid_value})

    with pytest.raises((GraphLifecycleIntegrityError, GraphLifecycleStateError)):
        lifecycle.acquire(
            invalid,
            worker_id="worker",
            lease_duration=timedelta(seconds=30),
        )

    persisted = repository.get_attempt(attempt.id)
    assert persisted is not None
    assert persisted.execution_count == 0
    assert persisted.state is ProjectionAttemptState.QUEUED


def test_expired_lease_recovery_reuses_attempt_and_generation(session: Session) -> None:
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    decision = lifecycle.reconcile_published(_header(), correlation_id="recover")
    attempt = decision.result.attempt
    assert attempt is not None
    now = datetime.now(UTC)
    first_lease = lifecycle.acquire(
        _work_payload(repository, attempt),
        worker_id="worker-old",
        lease_duration=timedelta(seconds=10),
        now=now,
    )
    assert first_lease is not None
    recovered = lifecycle.recover_expired(attempt.id, now=now + timedelta(seconds=11))
    assert recovered is not None
    assert recovered.id == attempt.id
    assert recovered.generation_id == attempt.generation_id
    assert recovered.state is ProjectionAttemptState.RETRYING
    assert (
        lifecycle.heartbeat(
            first_lease,
            lease_duration=timedelta(seconds=10),
            now=now + timedelta(seconds=11),
        )
        is None
    )
    replacement = lifecycle.acquire(
        _work_payload(repository, attempt),
        worker_id="worker-new",
        lease_duration=timedelta(seconds=10),
        now=now + timedelta(seconds=11),
    )
    assert replacement is not None
    assert replacement.token != first_lease.token
    assert replacement.generation_id == first_lease.generation_id


def test_three_execution_failures_are_terminal_but_owner_can_rebuild(
    session: Session,
) -> None:
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    decision = lifecycle.reconcile_published(_header(), correlation_id="retry")
    attempt = decision.result.attempt
    assert attempt is not None
    for execution in range(3):
        now = datetime.now(UTC) + timedelta(minutes=execution)
        lease = lifecycle.acquire(
            _work_payload(repository, attempt),
            worker_id="worker",
            lease_duration=timedelta(seconds=30),
            now=now,
        )
        assert lease is not None
        attempt = lifecycle.record_failure(
            lease,
            failure_code="NEO4J_UNAVAILABLE",
            failure_message="safe failure",
            transient=True,
            now=now + timedelta(seconds=1),
        )
    assert attempt.state is ProjectionAttemptState.FAILED
    resource = repository.get_resource(decision.result.resource.id)
    assert resource is not None and resource.state is ProjectionPublicState.FAILED

    with pytest.raises(GraphLifecycleStateError):
        lifecycle.request_rebuild(
            resource.id,
            actor_id=uuid4(),
            actor_role="VIEWER",
            correlation_id="denied",
        )
    rebuilt, payload = lifecycle.request_rebuild(
        resource.id,
        actor_id=uuid4(),
        actor_role="OWNER",
        correlation_id="rebuild",
    )
    assert rebuilt.attempt_number == 2
    assert rebuilt.generation_id == payload.generation_id
    assert rebuilt.actor_role == "owner"


def test_failed_rebuild_preserves_completed_and_stale_active_generation(
    session: Session,
) -> None:
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    repository_id = uuid4()
    first_header = _header(repository_id=repository_id, sequence=1)
    first = lifecycle.reconcile_published(first_header, correlation_id="initial")
    attempt = first.result.attempt
    assert attempt is not None
    _activate(
        lifecycle,
        repository,
        first_header,
        first.result.resource.id,
        attempt.id,
        attempt.generation_id,
    )
    active_generation = attempt.generation_id

    rebuild, _ = lifecycle.request_rebuild(
        first.result.resource.id,
        actor_id=uuid4(),
        actor_role="ADMIN",
        correlation_id="rebuild-completed",
    )
    now = datetime.now(UTC)
    lease = lifecycle.acquire(
        _work_payload(repository, rebuild),
        worker_id="worker",
        lease_duration=timedelta(minutes=1),
        now=now,
    )
    assert lease is not None
    lifecycle.record_failure(
        lease,
        failure_code="VERIFY_FAILED",
        failure_message="candidate invalid",
        transient=False,
        now=now + timedelta(seconds=1),
    )
    completed = repository.get_resource(first.result.resource.id)
    assert completed is not None
    assert completed.state is ProjectionPublicState.COMPLETED
    assert completed.active_generation_id == active_generation

    second_header = _header(repository_id=repository_id, sequence=2)
    lifecycle.reconcile_published(second_header, correlation_id="new-version")
    stale = repository.get_resource(first.result.resource.id)
    assert stale is not None and stale.state is ProjectionPublicState.STALE

    stale_rebuild, _ = lifecycle.request_rebuild(
        stale.id,
        actor_id=uuid4(),
        actor_role="OWNER",
        correlation_id="rebuild-stale",
    )
    later = now + timedelta(minutes=2)
    stale_lease = lifecycle.acquire(
        _work_payload(repository, stale_rebuild),
        worker_id="worker",
        lease_duration=timedelta(minutes=1),
        now=later,
    )
    assert stale_lease is not None
    lifecycle.record_failure(
        stale_lease,
        failure_code="VERIFY_FAILED",
        failure_message="candidate invalid",
        transient=False,
        now=later + timedelta(seconds=1),
    )
    still_stale = repository.get_resource(stale.id)
    assert still_stale is not None
    assert still_stale.state is ProjectionPublicState.STALE
    assert still_stale.active_generation_id == active_generation


def test_late_verification_result_cannot_switch_pointer(session: Session) -> None:
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    header = _header()
    decision = lifecycle.reconcile_published(header, correlation_id="late")
    attempt = decision.result.attempt
    assert attempt is not None
    now = datetime.now(UTC)
    lease = lifecycle.acquire(
        _work_payload(repository, attempt),
        worker_id="worker",
        lease_duration=timedelta(seconds=1),
        now=now,
    )
    assert lease is not None
    receipt = _successful_receipt(
        header=header,
        resource_id=decision.result.resource.id,
        attempt_id=attempt.id,
        generation_id=attempt.generation_id,
        lease_owner=lease.worker_id,
        lease_token=lease.token,
    )
    result = lifecycle.activate(receipt, now=now + timedelta(seconds=2))
    assert result.disposition is ActivationDisposition.REJECTED_STALE
    assert result.resource.active_generation_id is None


def test_failed_independent_verification_is_recorded_without_activation(
    session: Session,
) -> None:
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    header = _header()
    decision = lifecycle.reconcile_published(header, correlation_id="verify-fail")
    attempt = decision.result.attempt
    assert attempt is not None
    now = datetime.now(UTC)
    lease = lifecycle.acquire(
        _work_payload(repository, attempt),
        worker_id="worker",
        lease_duration=timedelta(minutes=1),
        now=now,
    )
    assert lease is not None
    receipt = _successful_receipt(
        header=header,
        resource_id=decision.result.resource.id,
        attempt_id=attempt.id,
        generation_id=attempt.generation_id,
        lease_owner=lease.worker_id,
        lease_token=lease.token,
    )
    receipt = replace(
        receipt,
        verified=False,
        failure_code="COUNT_MISMATCH",
        failure_message="Candidate counts do not match.",
    )
    result = lifecycle.activate(receipt, now=now + timedelta(seconds=1))
    assert result.disposition is ActivationDisposition.RECORDED_FAILURE
    assert result.resource.state is ProjectionPublicState.FAILED
    assert result.resource.active_generation_id is None


def test_failure_details_are_bounded_and_credentials_are_redacted(
    session: Session,
) -> None:
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    decision = lifecycle.reconcile_published(_header(), correlation_id="safe-error")
    attempt = decision.result.attempt
    assert attempt is not None
    now = datetime.now(UTC)
    lease = lifecycle.acquire(
        _work_payload(repository, attempt),
        worker_id="worker",
        lease_duration=timedelta(minutes=1),
        now=now,
    )
    assert lease is not None
    failed = lifecycle.record_failure(
        lease,
        failure_code="CONNECTION_FAILED",
        failure_message="password=hunter2 bolt://admin:secret@neo4j:7687 " + "x" * 600,
        transient=False,
        now=now + timedelta(seconds=1),
    )
    assert failed.failure_message is not None
    assert "hunter2" not in failed.failure_message
    assert "admin:secret" not in failed.failure_message
    assert len(failed.failure_message) <= 500
