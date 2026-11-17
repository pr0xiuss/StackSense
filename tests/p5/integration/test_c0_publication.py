"""C0 public retirement and boundary rejection against real PostgreSQL."""

from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import DeliveryContractError
from backend.platform.delivery.dependencies import build_attempt_retirement_reader
from backend.platform.delivery.persistence import DeliveryAttemptModel as Attempt
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.publication import (
    PublicationContractViolation,
    PublicationUnitOfWork,
)
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from tests.p5.delivery.test_contracts import binding
from tests.p5.delivery.test_rollout import budgets
from tests.p5.integration.test_delivery_postgres import (
    FixturePort,
    claimed,
    prepared,
    producer_table,
    scheduled,
)


def test_retirement_is_not_lease_expiry_and_contains_no_ownership_secret(
    delivery_engine,
):
    lease = claimed(delivery_engine)
    reader = build_attempt_retirement_reader(delivery_engine, budgets())
    assert reader.read_retirement(lease.identity) is None
    with Session(delivery_engine) as session, session.begin():
        session.execute(
            update(Attempt)
            .where(Attempt.id == lease.identity.attempt_id)
            .values(expires_at=func.clock_timestamp() - timedelta(seconds=1))
        )
    assert reader.read_retirement(lease.identity) is None
    with Session(delivery_engine) as session, session.begin():
        assert SqlAlchemyDeliveryRepository(session).recover(
            lease.identity.work.work_id,
            lease.identity.work.scope.project_id,
            max_executions=3,
            retry_seconds=0.01,
        )
    result = reader.read_retirement(lease.identity)
    assert result.outcome == "EXPIRED" and result.publication is None
    assert lease.secret not in result.model_dump_json()
    assert "lease_digest" not in result.model_dump_json()
    assert reader.read_retirement(lease.identity) == result
    with pytest.raises(DeliveryContractError):
        reader.read_retirement(
            lease.identity.model_copy(update={"fence": lease.identity.fence + 1})
        )
    assert (
        reader.read_retirement(
            lease.identity.model_copy(update={"attempt_id": uuid4()})
        )
        is None
    )


def test_read_retirement_cannot_see_uncommitted_completion_then_returns_exact_receipt(
    delivery_engine,
):
    table = producer_table(delivery_engine)
    lease, reader = claimed(delivery_engine), build_attempt_retirement_reader(
        delivery_engine, budgets()
    )
    candidate = prepared(lease)
    with PublicationUnitOfWork(
        delivery_engine, timeout_seconds=5.0, lock_timeout_ms=1000
    ) as uow:
        accepted = uow.complete(
            lease, candidate, lambda session: FixturePort(session, table, candidate)
        )
        assert reader.read_retirement(lease.identity) is None
        uow.commit()
    result = reader.read_retirement(lease.identity)
    assert result.outcome == "COMPLETED" and result.publication == accepted


@pytest.mark.parametrize("boundary", ["prepared", "accepted", "readiness"])
def test_unchecked_unsupported_contracts_poison_publication_and_leave_no_output(
    delivery_engine, boundary
):
    table = producer_table(delivery_engine)
    lease = claimed(delivery_engine)
    candidate = prepared(lease)

    class Port(FixturePort):
        def publish_prepared(self, prepared, context):
            value = super().publish_prepared(prepared, context)
            return (
                value.model_copy(update={"contract_version": "unsupported"})
                if boundary == "accepted"
                else value
            )

        def validate_ready(self, reference, context):
            value = super().validate_ready(reference, context)
            return (
                value.model_copy(update={"contract_version": "unsupported"})
                if boundary == "readiness"
                else value
            )

    if boundary == "prepared":
        candidate = candidate.model_copy(
            update={
                "candidate": candidate.candidate.model_copy(update={"sealed": False})
            }
        )
    with pytest.raises(ValidationError):
        with PublicationUnitOfWork(
            delivery_engine, timeout_seconds=5.0, lock_timeout_ms=1000
        ) as uow:
            uow.complete(
                lease, candidate, lambda session: Port(session, table, candidate)
            )
            uow.commit()
    with Session(delivery_engine) as session:
        assert session.scalar(select(func.count()).select_from(Output)) == 0
        assert session.scalar(select(func.count()).select_from(table)) == 0


def test_sql_after_final_authorization_poison_is_irreversible(delivery_engine):
    table = producer_table(delivery_engine)
    lease, borrowed = claimed(delivery_engine), []
    candidate = prepared(lease)

    def factory(session):
        borrowed.append(session)
        return FixturePort(session, table, candidate)

    with PublicationUnitOfWork(
        delivery_engine, timeout_seconds=5.0, lock_timeout_ms=1000
    ) as uow:
        uow.complete(lease, candidate, factory)
        with pytest.raises(PublicationContractViolation):
            borrowed[0].scalar(select(table.c.id))
        with pytest.raises(PublicationContractViolation):
            uow.commit()
    with Session(delivery_engine) as session:
        assert session.scalar(select(func.count()).select_from(Output)) == 0
        assert session.scalar(select(func.count()).select_from(table)) == 0


@pytest.mark.parametrize(
    "field", ["input_fingerprint", "bundle_fingerprint", "scope", "work_id"]
)
def test_durable_identity_mismatch_rejected_before_claim(delivery_engine, field):
    _, _, _, payload, _ = scheduled(delivery_engine)
    with Session(delivery_engine) as session, session.begin():
        work = session.get(Work, payload.work_id)
        identity = {**work.identity}
        identity[field] = (
            {**identity["scope"], "snapshot_id": str(uuid4())}
            if field == "scope"
            else str(uuid4()) if field == "work_id" else "f" * 64
        )
        work.identity = identity
    with pytest.raises(DeliveryContractError):
        with Session(delivery_engine) as session, session.begin():
            SqlAlchemyDeliveryRepository(session).claim(
                payload,
                binding(),
                "fixture-worker",
                max_executions=3,
                lease_seconds=30.0,
                execution_seconds=30.0,
            )
    with Session(delivery_engine) as session:
        assert session.scalar(select(func.count()).select_from(Attempt)) == 0


def test_enlisted_ports_share_transaction_identity_and_old_context_is_not_a_live_lease(
    delivery_engine,
):
    table, contexts = producer_table(delivery_engine), []
    lease = claimed(delivery_engine)
    candidate = prepared(lease)

    class Port(FixturePort):
        def publish_prepared(self, candidate, context):
            contexts.append(context)
            return super().publish_prepared(candidate, context)

        def validate_ready(self, reference, context):
            contexts.append(context)
            context.require_reference(reference)
            return super().validate_ready(reference, context)

    def factory(session):
        return Port(session, table, candidate)

    with PublicationUnitOfWork(
        delivery_engine, timeout_seconds=5.0, lock_timeout_ms=1000
    ) as uow:

        def dependencies(session, receipt):
            context = uow.context(receipt.prepared.attempt)
            uow.enlist(factory).validate_ready(receipt.accepted.reference, context)

        uow.complete(lease, candidate, factory, stage_dependencies=dependencies)
        assert len(contexts) == 3 and len({c.transaction_id for c in contexts}) == 1
        uow.commit()
    with PublicationUnitOfWork(
        delivery_engine, timeout_seconds=5.0, lock_timeout_ms=1000
    ) as uow:
        # A terminal attempt remains valid provenance for readiness, not a lease.
        context = uow.context(lease.identity)
        assert context.transaction_id != contexts[0].transaction_id


def test_swallowed_binding_rejection_cannot_authorize_a_different_transaction(
    delivery_engine,
):
    table = producer_table(delivery_engine)
    lease = claimed(delivery_engine)
    candidate = prepared(lease).model_copy(update={"contract_version": "unsupported"})
    with PublicationUnitOfWork(
        delivery_engine, timeout_seconds=5.0, lock_timeout_ms=1000
    ) as uow:
        with pytest.raises(ValidationError):
            uow.complete(
                lease, candidate, lambda session: FixturePort(session, table, candidate)
            )
        with pytest.raises(PublicationContractViolation):
            uow.coordinate(lambda session: None)


def test_persisted_dependency_rejects_unsupported_contract(delivery_engine):
    from backend.platform.delivery.persistence import DeliveryBundleModel as Bundle
    from tests.p5.delivery.test_barrier import complete, payload_for, setup

    runtime, scope, bundle_id, _ = setup(delivery_engine)
    complete(runtime, scope, bundle_id, "system_overview")
    with Session(delivery_engine) as session, session.begin():
        bundle = session.get(Bundle, bundle_id)
        bundle.sibling_release = {
            **bundle.sibling_release,
            "contract_version": "unsupported",
        }
    assert (
        runtime.execute(
            payload_for(runtime, scope, bundle_id, "component_architecture"),
            "test-worker",
        )
        == "failed"
    )
    with Session(delivery_engine) as session:
        assert session.scalar(select(func.count()).select_from(Output)) == 1
