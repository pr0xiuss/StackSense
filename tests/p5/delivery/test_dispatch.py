"""Durable intent survives broker errors and duplicate redispatch."""

from datetime import timedelta

from sqlalchemy import select

from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from tests.p5.delivery.test_rollout import RecordingPublisher, budgets, coordinator


def test_broker_failure_leaves_replayable_queued_intent(delivery_engine):
    publisher = RecordingPublisher(fail=True)
    runtime = coordinator(
        delivery_engine,
        publisher=publisher,
        runtime_budgets=budgets().model_copy(update={"redispatch_seconds": 30.0}),
    )
    runtime.heartbeat("test-worker")
    assert runtime.discover() == 1
    assert runtime.dispatch() == 0
    with runtime.session() as session, session.begin():
        work = session.scalars(
            select(Work).where(Work.kind == "search_projection")
        ).one()
        assert work.state == "QUEUED" and work.executions == 0
        assert work.dispatches == 1
        epoch = work.dispatch_epoch
        assert work.safe_reason == "broker_unavailable"
        work.dispatch_until = SqlAlchemyDeliveryRepository(session).now() - timedelta(
            seconds=1
        )
    publisher.fail = False
    assert runtime.dispatch() == 1
    assert publisher.payloads[0].dispatch_epoch == epoch
    assert runtime.dispatch() == 0


def test_bounded_window_advances_past_unavailable_and_reserved_work(delivery_engine):
    from backend.platform.delivery.model import Eligibility
    from tests.p5.delivery.test_contracts import scope

    runtime = coordinator(
        delivery_engine,
        runtime_budgets=budgets().model_copy(
            update={"max_items": 2, "revisit_seconds": 30.0, "redispatch_seconds": 30.0}
        ),
    )
    with runtime.session() as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        for _ in range(3):
            repo.ensure_bundle(
                scope(),
                runtime.policy,
                Eligibility.ELIGIBLE,
                revisit_seconds=30.0,
                runtime_profile=runtime.budgets.model_dump(mode="json"),
            )
    runtime.heartbeat("test-worker")
    for _ in range(4):
        runtime.dispatch()
    assert len({p.work_id for p in runtime.publisher.payloads}) == 3
