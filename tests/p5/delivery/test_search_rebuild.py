"""Additive M1-only completed-search successor change-control proofs.

These use real PostgreSQL and M1's publication UoW, not producer lifecycle code.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.delivery.api_contracts import DeliveryApiError, RetryRequest
from backend.platform.delivery.contracts import WorkIdentity, WorkKind
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.publication import PublicationUnitOfWork
from backend.platform.delivery.reprojection import (
    AuthorizedReprojectionPrincipal,
    SearchReprojectionOperation,
    SearchReprojectionPolicy,
    SearchReprojectionRequest,
    SearchReprojectionService,
)
from tests.p5.delivery.test_rollout import coordinator
from tests.p5.integration.test_delivery_postgres import (
    FixturePort,
    claimed,
    prepared,
    producer_table,
)


def completed_search(engine):
    SearchReprojectionOperation.__table__.create(engine)
    lease, table = claimed(engine), producer_table(engine)
    candidate = prepared(lease)
    with PublicationUnitOfWork(engine, timeout_seconds=10, lock_timeout_ms=1000) as uow:
        receipt = uow.complete(
            lease, candidate, lambda s: FixturePort(s, table, candidate)
        )
        uow.commit()
    runtime = coordinator(engine)
    runtime.heartbeat("test-worker")
    policy = SearchReprojectionPolicy(
        max_rounds=2, window_seconds=60, max_actor_requests=10, max_project_requests=20
    )
    service = SearchReprojectionService(runtime, policy)
    request = SearchReprojectionRequest(
        expected_predecessor_work_id=lease.identity.work.work_id,
        expected_accepted_reference=receipt.accepted.reference,
        reason="manual_rebuild",
        idempotency_key="rebuild-test",
    )
    return service, lease, request, receipt


def principal(lease, role="OWNER", actor=None):
    return AuthorizedReprojectionPrincipal(
        actor_id=actor or uuid4(),
        project_id=lease.identity.work.scope.project_id,
        role=role,
    )


def test_completed_search_rebuild_preserves_terminal_receipt_and_exact_input(
    delivery_engine,
):
    runtime, lease, request, receipt = completed_search(delivery_engine)
    actor = principal(lease)
    result = runtime.request_search_reprojection(
        lease.identity.work.scope, request, actor
    )
    assert (
        runtime.request_search_reprojection(lease.identity.work.scope, request, actor)
        == result
    )
    assert (
        runtime.lookup(lease.identity.work.scope, request.idempotency_key, actor)
        == result
    )
    with Session(delivery_engine) as session:
        prior = session.get(Work, request.expected_predecessor_work_id)
        successor = session.get(Work, result.new_work_id)
        identity = WorkIdentity.model_validate_json(json.dumps(successor.identity))
        assert prior.state == "COMPLETED" and not prior.is_current
        assert successor.is_current and successor.state == "PENDING"
        assert identity == lease.identity.work.model_copy(
            update={"work_id": result.new_work_id, "run_number": 2}
        )
        assert successor.retry_of_work_id is None
        assert successor.executions == successor.fence == 0
        assert successor.dispatch_epoch != lease.identity.dispatch_epoch
        assert session.scalar(
            select(Output).where(Output.work_id == prior.id)
        ).receipt == receipt.model_dump(mode="json")


def test_reprojection_migration_round_trip(delivery_engine):
    import importlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    migration = importlib.import_module(
        "backend.infra.migrations.versions.26c95d71b603_search_reprojection_requests"
    )
    schema = delivery_engine.get_execution_options()["schema_translate_map"][None]
    with delivery_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert "delivery_search_reprojections" in inspect(
                connection
            ).get_table_names(schema=schema)
            migration.downgrade()
            assert "delivery_search_reprojections" not in inspect(
                connection
            ).get_table_names(schema=schema)


@pytest.mark.parametrize("role", ["VIEWER", "MEMBER"])
def test_rebuild_rejects_nonprivileged_actor(delivery_engine, role):
    runtime, lease, request, _ = completed_search(delivery_engine)
    with pytest.raises(DeliveryApiError) as caught:
        runtime.request_search_reprojection(
            lease.identity.work.scope, request, principal(lease, role)
        )
    assert caught.value.status == 403


def test_rebuild_needs_explicit_policy_and_does_not_enable_normal_retry(
    delivery_engine,
):
    runtime, lease, request, _ = completed_search(delivery_engine)
    with pytest.raises(DeliveryApiError, match="retry_conflict"):
        runtime._runtime.retry(
            lease.identity.work.scope,
            RetryRequest(
                resource_type=WorkKind.SEARCH,
                resource_id=lease.identity.work.work_id,
                idempotency_key="retry-test",
            ),
            uuid4(),
            "OWNER",
        )
    runtime._policy = None
    with pytest.raises(DeliveryApiError, match="policy_unavailable"):
        runtime.request_search_reprojection(
            lease.identity.work.scope, request, principal(lease)
        )


def test_concurrent_search_rebuild_creates_one_successor(delivery_engine):
    runtime, lease, request, _ = completed_search(delivery_engine)

    def rebuild(key):
        try:
            return runtime.request_search_reprojection(
                lease.identity.work.scope,
                request.model_copy(update={"idempotency_key": key}),
                principal(lease, "ADMIN"),
            )
        except DeliveryApiError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(rebuild, ["first", "second"]))
    assert sum(not isinstance(result, str) for result in results) == 1
    assert "delivery_reprojection_conflict" in results


def test_altered_reference_and_unapproved_automatic_repair_rejected(delivery_engine):
    service, lease, request, _ = completed_search(delivery_engine)
    reference = request.expected_accepted_reference
    altered = request.model_copy(
        update={
            "expected_accepted_reference": reference.model_copy(
                update={"artifact_id": uuid4()}
            )
        }
    )
    with pytest.raises(DeliveryApiError, match="reference_conflict"):
        service.request_search_reprojection(
            lease.identity.work.scope, altered, principal(lease)
        )
    with pytest.raises(DeliveryApiError, match="automatic_repair_unavailable"):
        service.request_search_reprojection(
            lease.identity.work.scope,
            request.model_copy(
                update={"reason": "storage_corrupt", "observation_id": uuid4()}
            ),
            principal(lease),
        )


def test_idempotency_body_conflict_and_foreign_principal(delivery_engine):
    service, lease, request, _ = completed_search(delivery_engine)
    actor = principal(lease)
    result = service.request_search_reprojection(
        lease.identity.work.scope, request, actor
    )
    altered = request.model_copy(update={"expected_predecessor_work_id": uuid4()})
    with pytest.raises(DeliveryApiError, match="idempotency_conflict"):
        service.request_search_reprojection(lease.identity.work.scope, altered, actor)
    with pytest.raises(DeliveryApiError, match="forbidden"):
        service.lookup(
            lease.identity.work.scope,
            request.idempotency_key,
            actor.model_copy(update={"project_id": uuid4()}),
        )
    for key in ["x" * 129, "invalid/key"]:
        with pytest.raises(ValidationError):
            service.lookup(lease.identity.work.scope, key, actor)
    with Session(delivery_engine) as session:
        from backend.platform.delivery.persistence import DeliveryRetryRequestModel

        assert session.scalar(select(DeliveryRetryRequestModel.id)) is None
        work = session.get(Work, result.new_work_id)
        # Durable replay must not depend on today's active slot/state.
        work.state = "FAILED"
        session.commit()
    assert (
        service.lookup(lease.identity.work.scope, request.idempotency_key, actor)
        == result
    )
    assert (
        service.request_search_reprojection(lease.identity.work.scope, request, actor)
        == result
    )


def test_rebuild_rejects_malformed_input_binding_and_preserves_other_slots(
    delivery_engine,
):
    from backend.platform.delivery.persistence import DeliveryBundleModel

    service, lease, request, receipt = completed_search(delivery_engine)
    with Session(delivery_engine) as session:
        before = [
            (w.id, w.identity, w.state)
            for w in session.scalars(select(Work).where(Work.kind != WorkKind.SEARCH))
        ]
        barrier = session.get(
            DeliveryBundleModel, lease.identity.work.bundle_id
        ).barrier
    ref = request.expected_accepted_reference
    malformed = request.model_copy(
        update={
            "expected_accepted_reference": ref.model_copy(
                update={"input_fingerprint": "f" * 64}
            )
        }
    )
    with pytest.raises(DeliveryApiError, match="conflict"):
        service.request_search_reprojection(
            lease.identity.work.scope, malformed, principal(lease)
        )
    service.request_search_reprojection(
        lease.identity.work.scope, request, principal(lease)
    )
    with Session(delivery_engine) as session:
        assert before == [
            (w.id, w.identity, w.state)
            for w in session.scalars(select(Work).where(Work.kind != WorkKind.SEARCH))
        ]
        assert (
            barrier
            == session.get(DeliveryBundleModel, lease.identity.work.bundle_id).barrier
        )
        assert session.scalar(
            select(Output).where(Output.work_id == lease.identity.work.work_id)
        ).receipt == receipt.model_dump(mode="json")
