"""Durable graph discovery, dispatch, and recovery behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.graph.lifecycle import (
    GraphProjectionLifecycle,
    GraphProjectionReconciler,
)
from backend.platform.graph.model import ProjectionCounts
from backend.platform.graph.persistence import SqlAlchemyGraphProjectionRepository
from backend.platform.graph.queue import InMemoryProjectionPublisher
from backend.platform.graph.source import (
    PublishedArchitectureHeader,
    PublishedArchitecturePage,
)
from backend.platform.projects.infra.base import Base


class SourceStub:
    def __init__(self, headers: tuple[PublishedArchitectureHeader, ...]) -> None:
        self.headers = headers

    def list_published(
        self, *, limit: int, after: object = None
    ) -> PublishedArchitecturePage:
        del limit, after
        return PublishedArchitecturePage(items=self.headers, next_cursor=None)

    def load_exact(self, architecture_version_id: UUID, project_id: UUID) -> None:
        del architecture_version_id, project_id
        return None


class FailingPublisher(InMemoryProjectionPublisher):
    def publish(self, payload: object) -> None:
        del payload
        raise ConnectionError("broker details must not alter durable intent")


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value
    engine.dispose()


def _header() -> PublishedArchitectureHeader:
    return PublishedArchitectureHeader(
        contract_version="1.0.0",
        architecture_version_id=uuid4(),
        analysis_id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        sequence_number=1,
        published_at=datetime.now(UTC),
        configuration_fingerprint="configuration",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        content_digest="source",
        counts=ProjectionCounts(2, 1, 3, 0, 0),
    )


def _reconciler(
    session: Session,
    *,
    header: PublishedArchitectureHeader,
    publisher: InMemoryProjectionPublisher,
    ready: bool,
) -> GraphProjectionReconciler:
    return GraphProjectionReconciler(
        source=SourceStub((header,)),
        repository=SqlAlchemyGraphProjectionRepository(session),
        publisher=publisher,
        checkpoint=session.commit,
        rollback=session.rollback,
        execution_ready=lambda: ready,
        page_size=100,
        recovery_batch_size=100,
        dispatch_recovery_after=timedelta(seconds=30),
        retry_backoff=timedelta(seconds=5),
    )


def test_absent_executor_preserves_one_undispatched_attempt(session: Session) -> None:
    header = _header()
    publisher = InMemoryProjectionPublisher()
    reconciler = _reconciler(session, header=header, publisher=publisher, ready=False)
    now = datetime.now(UTC)

    first = reconciler.reconcile(correlation_id="first", now=now)
    second = reconciler.reconcile(correlation_id="second", now=now)

    assert first.resources_created == 1
    assert second.resources_created == 0
    assert first.dispatch_candidates == second.dispatch_candidates == 1
    assert first.dispatch_enabled is second.dispatch_enabled is False
    assert publisher.published == []
    result = SqlAlchemyGraphProjectionRepository(session).ensure_with_initial_attempt(
        header, correlation_id="inspect"
    )
    assert result.attempt is not None
    assert result.attempt.dispatch_count == 0


def test_dispatch_recovery_reuses_exact_attempt_and_generation(
    session: Session,
) -> None:
    header = _header()
    publisher = InMemoryProjectionPublisher()
    reconciler = _reconciler(session, header=header, publisher=publisher, ready=True)
    now = datetime.now(UTC)

    first = reconciler.reconcile(correlation_id="first", now=now)
    too_soon = reconciler.reconcile(
        correlation_id="too-soon", now=now + timedelta(seconds=29)
    )
    recovered = reconciler.reconcile(
        correlation_id="recover", now=now + timedelta(seconds=31)
    )

    assert first.dispatched == 1
    assert too_soon.dispatch_candidates == 0
    assert recovered.dispatched == 1
    assert len(publisher.published) == 2
    assert publisher.published[0].attempt_id == publisher.published[1].attempt_id
    assert publisher.published[0].generation_id == publisher.published[1].generation_id


def test_broker_failure_keeps_durable_attempt_eligible(session: Session) -> None:
    header = _header()
    reconciler = _reconciler(
        session, header=header, publisher=FailingPublisher(), ready=True
    )

    failed = reconciler.reconcile(correlation_id="failure", now=datetime.now(UTC))

    assert failed.publish_failures == 1
    result = SqlAlchemyGraphProjectionRepository(session).ensure_with_initial_attempt(
        header, correlation_id="inspect"
    )
    assert result.attempt is not None
    assert result.attempt.dispatch_count == 0
    assert result.attempt.dispatched_at is None


def test_crash_after_publish_is_recovered_as_safe_duplicate(session: Session) -> None:
    header = _header()
    publisher = InMemoryProjectionPublisher()
    repository = SqlAlchemyGraphProjectionRepository(session)
    commits = 0

    def crash_after_publish() -> None:
        nonlocal commits
        commits += 1
        if commits == 2:
            session.rollback()
            raise RuntimeError("simulated crash after broker publish")
        session.commit()

    first = GraphProjectionReconciler(
        source=SourceStub((header,)),
        repository=repository,
        publisher=publisher,
        checkpoint=crash_after_publish,
        rollback=session.rollback,
        execution_ready=lambda: True,
        page_size=100,
        recovery_batch_size=100,
        dispatch_recovery_after=timedelta(seconds=30),
        retry_backoff=timedelta(seconds=5),
    )
    now = datetime.now(UTC)

    with pytest.raises(RuntimeError, match="simulated crash"):
        first.reconcile(correlation_id="crash", now=now)
    recovered = _reconciler(
        session, header=header, publisher=publisher, ready=True
    ).reconcile(correlation_id="recover", now=now + timedelta(seconds=1))

    assert recovered.dispatched == 1
    assert len(publisher.published) == 2
    assert publisher.published[0].attempt_id == publisher.published[1].attempt_id
    assert publisher.published[0].generation_id == publisher.published[1].generation_id


def test_expired_worker_recovers_same_intent_without_immediate_retry(
    session: Session,
) -> None:
    header = _header()
    repository = SqlAlchemyGraphProjectionRepository(session)
    lifecycle = GraphProjectionLifecycle(repository)
    decision = lifecycle.reconcile_published(header, correlation_id="initial")
    assert decision.result.attempt is not None
    original = decision.result.attempt
    start = datetime.now(UTC)
    lease = lifecycle.acquire(
        GraphProjectionLifecycle.payload_for(
            original.resource_id, repository, original
        ),
        worker_id="lost-worker",
        lease_duration=timedelta(seconds=10),
        now=start,
    )
    assert lease is not None
    session.commit()
    publisher = InMemoryProjectionPublisher()
    reconciler = _reconciler(session, header=header, publisher=publisher, ready=True)

    recovered = reconciler.reconcile(
        correlation_id="recover", now=start + timedelta(seconds=11)
    )
    dispatched = reconciler.reconcile(
        correlation_id="dispatch", now=start + timedelta(seconds=17)
    )

    assert recovered.expired_leases_recovered == 1
    assert recovered.dispatched == 0
    assert dispatched.dispatched == 1
    assert publisher.published[0].attempt_id == original.id
    assert publisher.published[0].generation_id == original.generation_id
