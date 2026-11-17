"""Fleet admission requires fresh compatible evidence from every consumer."""

from contextlib import contextmanager

from backend.platform.delivery.contracts import DiagramTemplate, WorkKind
from backend.platform.delivery.registry import HandlerRegistration, WorkHandlerRegistry
from backend.platform.delivery.service import (
    DeliveryCoordinator,
    FleetManifest,
    RuntimeBudgets,
)
from backend.platform.delivery.source import PublishedVersionReader
from tests.p5.delivery.test_contracts import binding
from tests.p5.delivery.test_source import PublicSourceFixture
from tests.p5.integration.test_delivery_postgres import policy


def budgets():
    # Explicit fixture settings, not proposed/approved production defaults.
    return RuntimeBudgets(
        lease_seconds=10.0,
        heartbeat_seconds=0.1,
        execution_seconds=20.0,
        publication_seconds=5.0,
        lock_timeout_ms=1000,
        max_executions=3,
        retry_seconds=0.01,
        retry_max_seconds=1.0,
        retry_jitter_fraction=0.0,
        redispatch_seconds=0.05,
        reservation_seconds=1.0,
        capability_ttl_seconds=30.0,
        scan_seconds=5.0,
        scan_lease_seconds=10.0,
        revisit_seconds=0.01,
        broker_timeout_seconds=1.0,
        reconcile_seconds=1.0,
        max_items=10,
        quarantine_max_records=50,
        page_size=5,
        per_project_running=2,
    )


class RecordingPublisher:
    def __init__(self, fail=False):
        self.payloads, self.fail = [], fail

    def publish(self, payload):
        if self.fail:
            raise ConnectionError("fixture unavailable")
        self.payloads.append(payload)


def coordinator(
    engine,
    *,
    publisher=None,
    workers=("test-worker",),
    reader_source=None,
    registry=None,
    queue="fixture.queue",
    runtime_budgets=None,
):
    source = reader_source or PublicSourceFixture()

    @contextmanager
    def reader():
        yield PublishedVersionReader(source, source.get_analysis)

    class UnusedHandler:
        def execute(self, context):
            raise AssertionError("not expected in fleet test")

    registry = registry or WorkHandlerRegistry(
        (HandlerRegistration(binding(), UnusedHandler(), lambda s: None),)
    )
    return DeliveryCoordinator(
        engine=engine,
        registry=registry,
        publisher=publisher or RecordingPublisher(),
        policy=policy(runtime_budgets),
        budgets=runtime_budgets or budgets(),
        fleet=FleetManifest(
            queue=queue,
            deployment_epoch="test-epoch",
            workers=workers,
            admission_approved=True,
        ),
        reader=reader,
        dispatch_enabled=True,
    )


def test_all_peers_need_matching_profile_and_unknown_peer_blocks(delivery_engine):
    runtime = coordinator(delivery_engine, workers=("one", "two"))
    runtime.heartbeat("one")
    with runtime.session() as session:
        assert not runtime.fleet_ready(session, binding())
    runtime.heartbeat("two")
    with runtime.session() as session:
        assert runtime.fleet_ready(session, binding())
        assert not runtime.fleet_ready(
            session, binding(WorkKind.DIAGRAM, DiagramTemplate.OVERVIEW)
        )
    runtime.heartbeat("unknown")
    with runtime.session() as session:
        assert not runtime.fleet_ready(session, binding())


def test_disabled_dispatch_produces_no_messages(delivery_engine):
    runtime = coordinator(delivery_engine)
    runtime.dispatch_enabled = False
    assert runtime.dispatch() == 0
    assert runtime.publisher.payloads == []


def test_seeded_retry_backoff_is_bounded_without_affecting_fingerprints(
    delivery_engine,
):
    from random import Random

    settings = budgets().model_copy(update={"retry_jitter_fraction": 0.2})
    first, second = coordinator(delivery_engine, runtime_budgets=settings), coordinator(
        delivery_engine, runtime_budgets=settings
    )
    first._rng, second._rng = Random(123), Random(123)
    delays = [first.retry_delay(n) for n in (1, 2, 3, 1000000)]
    assert delays == [second.retry_delay(n) for n in (1, 2, 3, 1000000)]
    assert all(0 <= delay <= settings.retry_max_seconds for delay in delays)


def test_changed_runtime_profile_does_not_consume_existing_run(delivery_engine):
    from sqlalchemy import select

    from backend.platform.delivery.persistence import DeliveryWorkModel as Work

    original = coordinator(delivery_engine)
    original.discover()
    original.heartbeat("test-worker")
    assert original.dispatch() == 1
    payload = original.publisher.payloads[0]
    changed = coordinator(
        delivery_engine,
        runtime_budgets=budgets().model_copy(update={"max_executions": 4}),
    )
    changed.heartbeat("test-worker")
    assert changed.execute(payload, "test-worker") == "runtime_profile_unavailable"
    with changed.session() as session:
        assert (
            session.scalar(select(Work.executions).where(Work.id == payload.work_id))
            == 0
        )
