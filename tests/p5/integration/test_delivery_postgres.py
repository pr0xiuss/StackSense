"""Independent-connection PostgreSQL race/rollback/publication proofs."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import (
    Column,
    MetaData,
    String,
    Table,
    Uuid,
    event,
    insert,
    select,
    update,
)
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AcceptedOutput,
    ArtifactReference,
    CandidateSeal,
    DeliveryPolicy,
    OutputDigests,
    PreparedOutput,
    WorkKind,
)
from backend.platform.delivery.model import (
    CancellationCause,
    CancellationDecision,
    Eligibility,
)
from backend.platform.delivery.persistence import DeliveryAttemptModel as Attempt
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.publication import (
    PublicationContractViolation,
    PublicationUnitOfWork,
    ReadyValidation,
)
from backend.platform.delivery.repository import (
    DeliveryOwnershipLost,
    SqlAlchemyDeliveryRepository,
)
from tests.p5.delivery.test_contracts import binding, scope


def policy(runtime_budgets=None):
    from backend.platform.delivery.contracts import DiagramTemplate, fingerprint
    from tests.p5.delivery.test_rollout import budgets

    return DeliveryPolicy(
        policy_version="test-v1",
        execution_policy_fingerprint=fingerprint(
            "delivery.runtime", runtime_budgets or budgets()
        ),
        profiles=(
            binding(),
            binding(WorkKind.REPORT),
            *(binding(WorkKind.DIAGRAM, t) for t in DiagramTemplate),
        ),
    )


def scheduled(engine):
    from tests.p5.delivery.test_rollout import budgets

    source, selected = scope(), policy()
    with Session(engine) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        bundle_id = repo.ensure_bundle(
            source,
            selected,
            Eligibility.ELIGIBLE,
            revisit_seconds=1.0,
            runtime_profile=budgets().model_dump(mode="json"),
        )
        work_id = session.scalar(
            select(Work.id).where(
                Work.bundle_id == bundle_id, Work.kind == "search_projection"
            )
        )
        payload, reservation = repo.reserve(
            work_id,
            source.project_id,
            reservation_seconds=2.0,
            correlation_id="test:one",
        )
    return source, selected, bundle_id, payload, reservation


def claimed(engine):
    source, selected, bundle_id, payload, reservation = scheduled(engine)
    with Session(engine) as session, session.begin():
        lease = SqlAlchemyDeliveryRepository(session).claim(
            payload,
            binding(),
            "test-worker",
            max_executions=3,
            lease_seconds=60.0,
            execution_seconds=120.0,
        )
    assert lease is not None
    return lease


def prepared(lease):
    return PreparedOutput(
        attempt=lease.identity,
        candidate=CandidateSeal(
            generation_id=uuid4(),
            artifact_id=uuid4(),
            size_bytes=12,
            digests=OutputDigests(content="a" * 64),
            sealed=True,
        ),
    )


class FixturePort:
    def __init__(self, session, table, candidate, hook=None):
        self.session, self.table, self.candidate, self.hook = (
            session,
            table,
            candidate,
            hook,
        )

    def publish_prepared(self, candidate, context):
        context.require_prepared(candidate)
        self.session.execute(
            insert(self.table).values(
                id=candidate.candidate.generation_id,
                digest=candidate.candidate.digests.content,
            )
        )
        if self.hook:
            self.hook(self.session)
        work, seal = candidate.attempt.work, candidate.candidate
        return AcceptedOutput(
            reference=ArtifactReference(
                scope=work.scope,
                binding=work.binding,
                input_fingerprint=work.input_fingerprint,
                resource_id=uuid4(),
                candidate_id=candidate.attempt.candidate_id,
                generation_id=seal.generation_id,
                artifact_id=seal.artifact_id,
                size_bytes=seal.size_bytes,
                digests=seal.digests,
                sealed=True,
            )
        )

    def validate_ready(self, reference, context):
        assert (
            self.session.scalar(
                select(self.table.c.digest).where(
                    self.table.c.id == reference.generation_id
                )
            )
            == reference.digests.content
        )
        return ReadyValidation(reference=reference)


def producer_table(engine):
    table = Table(
        "fixture_producer",
        MetaData(),
        Column("id", Uuid, primary_key=True),
        Column("digest", String, nullable=False),
    )
    table.create(engine)
    return table


def test_same_physical_transaction_private_until_commit(delivery_engine):
    lease, table = claimed(delivery_engine), producer_table(delivery_engine)
    candidate = prepared(lease)
    with PublicationUnitOfWork(
        delivery_engine, timeout_seconds=10.0, lock_timeout_ms=1000
    ) as uow:
        receipt = uow.complete(
            lease, candidate, lambda s: FixturePort(s, table, candidate)
        )
        with Session(delivery_engine) as observer:
            assert observer.scalar(select(table.c.id)) is None
            assert observer.scalar(select(Output.id)) is None
            assert observer.get(Work, lease.identity.work.work_id).state == "RUNNING"
        uow.commit()
    with Session(delivery_engine) as observer:
        assert observer.scalar(select(Output.id)) == receipt.receipt_id
        assert observer.scalar(select(table.c.id)) == candidate.candidate.generation_id
        assert observer.get(Work, lease.identity.work.work_id).state == "COMPLETED"
        assert observer.get(Attempt, lease.identity.attempt_id).state == "COMPLETED"
        assert observer.get(Attempt, lease.identity.attempt_id).lease_digest is None


@pytest.mark.parametrize(
    "operation", ["commit", "rollback", "close", "connection", "get_bind", "dispatch"]
)
def test_caught_illegal_session_operation_poison_rolls_everything_back(
    delivery_engine, operation
):
    lease, table = claimed(delivery_engine), producer_table(delivery_engine)
    candidate = prepared(lease)

    def illegal(session):
        try:
            value = getattr(session, operation)
            value()
        except PublicationContractViolation:
            pass

    with pytest.raises(PublicationContractViolation):
        with PublicationUnitOfWork(
            delivery_engine, timeout_seconds=10.0, lock_timeout_ms=1000
        ) as uow:
            uow.complete(
                lease, candidate, lambda s: FixturePort(s, table, candidate, illegal)
            )
            uow.commit()
    with Session(delivery_engine) as session:
        assert session.scalar(select(table.c.id)) is None
        assert session.scalar(select(Output.id)) is None
        assert session.get(Work, lease.identity.work.work_id).state == "RUNNING"


def test_producer_event_registration_poisoned_before_callback(delivery_engine):
    lease, table = claimed(delivery_engine), producer_table(delivery_engine)
    candidate, callbacks = prepared(lease), []

    def register(session):
        try:
            event.listen(session, "after_commit", lambda *a: callbacks.append(True))
        except PublicationContractViolation:
            pass

    with pytest.raises(PublicationContractViolation):
        with PublicationUnitOfWork(
            delivery_engine, timeout_seconds=10.0, lock_timeout_ms=1000
        ) as uow:
            uow.complete(
                lease, candidate, lambda s: FixturePort(s, table, candidate, register)
            )
            uow.commit()
    assert callbacks == []


@pytest.mark.parametrize(
    "failure", ["hook", "receipt", "dependencies", "expiry", "no_commit"]
)
def test_publication_failure_boundaries_leave_no_partial_ready(
    delivery_engine, failure
):
    lease, table = claimed(delivery_engine), producer_table(delivery_engine)
    candidate = prepared(lease)

    def injected(session):
        if failure == "hook":
            raise RuntimeError("fixture hook failure")
        if failure == "expiry":
            session.execute(
                update(Attempt)
                .where(Attempt.id == lease.identity.attempt_id)
                .values(
                    expires_at=SqlAlchemyDeliveryRepository(session._session).now()
                    - timedelta(seconds=1)
                )
            )

    def stage(session, receipt):
        if failure == "dependencies":
            raise RuntimeError("fixture dependency failure")

    class BadReceipt(FixturePort):
        def publish_prepared(self, prepared, context):
            accepted = super().publish_prepared(prepared, context)
            return accepted.model_copy(
                update={
                    "reference": accepted.reference.model_copy(
                        update={"generation_id": uuid4()}
                    )
                }
            )

    try:
        with PublicationUnitOfWork(
            delivery_engine, timeout_seconds=10.0, lock_timeout_ms=1000
        ) as uow:
            uow.complete(
                lease,
                candidate,
                lambda s: (BadReceipt if failure == "receipt" else FixturePort)(
                    s, table, candidate, injected
                ),
                stage_dependencies=stage,
            )
            if failure != "no_commit":
                uow.commit()
    except RuntimeError, ValueError:
        assert failure != "no_commit"
    with Session(delivery_engine) as session:
        assert session.scalar(select(table.c.id)) is None
        assert session.scalar(select(Output.id)) is None
        assert session.get(Work, lease.identity.work.work_id).state == "RUNNING"


def test_two_independent_claims_acquire_one_execution(delivery_engine):
    _, _, _, payload, _ = scheduled(delivery_engine)

    def claim():
        with Session(delivery_engine) as session, session.begin():
            return SqlAlchemyDeliveryRepository(session).claim(
                payload,
                binding(),
                "test-worker",
                max_executions=3,
                lease_seconds=30.0,
                execution_seconds=60.0,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sum(r is not None for r in results) == 1
    with Session(delivery_engine) as session:
        assert session.get(Work, payload.work_id).executions == 1


def test_expired_renewal_stale_publication_and_recovery_preserve_history(
    delivery_engine,
):
    lease = claimed(delivery_engine)
    with Session(delivery_engine) as session, session.begin():
        now = SqlAlchemyDeliveryRepository(session).now()
        session.execute(
            update(Attempt)
            .where(Attempt.id == lease.identity.attempt_id)
            .values(expires_at=now - timedelta(seconds=1))
        )
    with Session(delivery_engine) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        assert not repo.renew(lease, lease_seconds=30.0)
        assert repo.recover(
            lease.identity.work.work_id,
            lease.identity.work.scope.project_id,
            max_executions=3,
            retry_seconds=0.001,
        )
    with PublicationUnitOfWork(
        delivery_engine, timeout_seconds=10.0, lock_timeout_ms=1000
    ) as uow:
        with pytest.raises(DeliveryOwnershipLost):
            uow.complete(
                lease, prepared(lease), lambda _: pytest.fail("stale producer invoked")
            )
    with Session(delivery_engine) as session:
        assert session.get(Attempt, lease.identity.attempt_id).state == "EXPIRED"
        assert session.get(Work, lease.identity.work.work_id).state == "RETRYING"


def test_cancel_fences_live_worker_and_terminal_history(delivery_engine):
    lease = claimed(delivery_engine)
    decision = CancellationDecision(
        CancellationCause.ADMINISTRATIVE_WITHDRAWAL,
        uuid4(),
        uuid4(),
        lease.identity.work.work_id,
        lease.identity.fence,
    )
    with Session(delivery_engine) as session, session.begin():
        assert SqlAlchemyDeliveryRepository(session).cancel(
            lease.identity.work.scope.project_id, decision
        )
    with Session(delivery_engine) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        assert not repo.renew(lease, lease_seconds=30.0)
        assert not repo.cancel(lease.identity.work.scope.project_id, decision)
        assert session.get(Attempt, lease.identity.attempt_id).state == "CANCELLED"


def test_bundle_and_slot_idempotency(delivery_engine):
    source, selected, bundle_id, _, _ = scheduled(delivery_engine)
    with Session(delivery_engine) as session, session.begin():
        assert (
            SqlAlchemyDeliveryRepository(session).ensure_bundle(
                source, selected, Eligibility.ELIGIBLE, revisit_seconds=1.0
            )
            == bundle_id
        )
        assert len(tuple(session.scalars(select(Work)))) == 5


@pytest.mark.parametrize(
    "operation",
    [
        "orm_commit",
        "orm_rollback",
        "orm_close",
        "raw_commit",
        "raw_rollback",
        "driver_sql",
        "result_context",
    ],
)
def test_borrowed_orm_and_result_escape_cannot_control_outer_transaction(
    delivery_engine, operation
):
    lease, table = claimed(delivery_engine), producer_table(delivery_engine)
    candidate = prepared(lease)

    def inject(borrowed):
        # Fault injection of handles also obtainable with SQLAlchemy's public
        # object_session(entity). The interface itself exposes no such handle.
        try:
            if operation.startswith("orm_"):
                getattr(borrowed._session, operation[4:])()
            elif operation == "raw_commit":
                borrowed._session.get_bind().commit()
            elif operation == "raw_rollback":
                borrowed._session.get_bind().rollback()
            elif operation == "driver_sql":
                borrowed._session.get_bind().exec_driver_sql("COMMIT")
            else:
                _ = borrowed.execute(select(table)).context
        except PublicationContractViolation:
            pass

    with pytest.raises(PublicationContractViolation):
        with PublicationUnitOfWork(
            delivery_engine, timeout_seconds=10.0, lock_timeout_ms=1000
        ) as uow:
            uow.complete(
                lease, candidate, lambda s: FixturePort(s, table, candidate, inject)
            )
            uow.commit()
    with Session(delivery_engine) as session:
        assert session.scalar(select(table.c.id)) is None
        assert session.scalar(select(Output.id)) is None
