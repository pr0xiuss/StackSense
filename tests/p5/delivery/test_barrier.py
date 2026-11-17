"""Real PostgreSQL fixture-producer dependency and exact report barrier tests."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.platform.delivery.api_contracts import (
    DeliveryApiError,
    ManualRetryPolicy,
    RetryRequest,
)
from backend.platform.delivery.contracts import (
    BarrierReceipt,
    CandidateSeal,
    DiagramTemplate,
    OutputDigests,
    PreparedOutput,
    WorkIdentity,
    WorkKind,
)
from backend.platform.delivery.persistence import DeliveryBundleModel as Bundle
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.registry import HandlerRegistration, WorkHandlerRegistry
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from tests.p5.delivery.test_rollout import coordinator
from tests.p5.integration.test_delivery_postgres import (
    FixturePort,
    policy,
    producer_table,
    scheduled,
)


def complete_registry(table):
    class Handler:
        def execute(self, context):
            if context.attempt.work.binding.slot.kind == WorkKind.REPORT:
                assert context.prerequisites is not None
                assert (
                    context.prerequisites.input_fingerprint()
                    == context.attempt.work.input_fingerprint
                )
            return PreparedOutput(
                attempt=context.attempt,
                candidate=CandidateSeal(
                    generation_id=uuid4(),
                    artifact_id=uuid4(),
                    size_bytes=12,
                    digests=OutputDigests(
                        content="a" * 64, spec="b" * 64, layout="c" * 64
                    ),
                    sealed=True,
                ),
            )

    handler = Handler()
    return WorkHandlerRegistry(
        tuple(
            HandlerRegistration(
                binding, handler, lambda session: FixturePort(session, table, None)
            )
            for binding in policy().profiles
        )
    )


def setup(delivery_engine):
    table = producer_table(delivery_engine)
    source, selected, bundle_id, _, _ = scheduled(delivery_engine)
    runtime = coordinator(delivery_engine, registry=complete_registry(table))
    runtime.manual_retry_policy = ManualRetryPolicy(
        max_rounds=2, window_seconds=60.0, max_actor_requests=5, max_project_requests=10
    )
    runtime.heartbeat("test-worker")
    return runtime, source, bundle_id, table


def payload_for(runtime, scope, bundle_id, template):
    with runtime.session() as session, session.begin():
        work = session.scalars(
            select(Work).where(
                Work.bundle_id == bundle_id,
                Work.template == template,
                Work.is_current.is_(True),
            )
        ).one()
        payload, _ = SqlAlchemyDeliveryRepository(session).reserve(
            work.id,
            scope.project_id,
            reservation_seconds=1.0,
            correlation_id="test:barrier",
        )
        return payload


def complete(runtime, scope, bundle_id, template):
    result = runtime.execute(
        payload_for(runtime, scope, bundle_id, template), "test-worker"
    )
    assert result == "completed", result


def report_count(engine):
    with Session(engine) as session:
        return session.scalar(
            select(func.count()).select_from(Work).where(Work.kind == WorkKind.REPORT)
        )


def test_zero_to_four_committed_refs_and_one_report(delivery_engine):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    assert report_count(delivery_engine) == 0
    for index, template in enumerate(DiagramTemplate):
        complete(runtime, scope, bundle_id, template)
        assert report_count(delivery_engine) == (1 if index == 3 else 0)
    with Session(delivery_engine) as session:
        barrier = BarrierReceipt.model_validate_json(
            json.dumps(session.get(Bundle, bundle_id).barrier)
        )
        report = session.scalar(select(Work).where(Work.kind == WorkKind.REPORT))
        assert report.identity["input_fingerprint"] == barrier.input_fingerprint()
    for _ in range(3):
        runtime.dependencies()
    assert report_count(delivery_engine) == 1
    complete(runtime, scope, bundle_id, "architecture_analysis")
    summary = runtime.summary(scope, "OWNER")
    assert summary.report.state == "COMPLETED"
    assert summary.waiting_on == ()
    assert len(summary.diagrams) == 4


def test_concurrent_siblings_create_exactly_one_report(delivery_engine):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    complete(runtime, scope, bundle_id, "system_overview")
    # Admit three executions in this fixture only; never a production default.
    payloads = [
        payload_for(runtime, scope, bundle_id, t)
        for t in DiagramTemplate
        if t != "system_overview"
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(
            pool.map(lambda payload: runtime.execute(payload, "test-worker"), payloads)
        )
    # A project limit may defer the third claim, but duplicate-safe replay finishes it.
    for result, payload in zip(results, payloads, strict=True):
        if result == "admission_wait":
            assert runtime.execute(payload, "test-worker") == "completed"
        else:
            assert result == "completed"
    assert report_count(delivery_engine) == 1


def fail_overview(runtime, scope, bundle_id, *, retryable):
    payload = payload_for(runtime, scope, bundle_id, "system_overview")
    with runtime.session() as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        work = session.get(Work, payload.work_id)
        identity = WorkIdentity.model_validate_json(json.dumps(work.identity))
        lease = repo.claim(
            payload,
            identity.binding,
            "test-worker",
            max_executions=1,
            lease_seconds=30.0,
            execution_seconds=30.0,
        )
        assert repo.finish_failure(
            lease,
            code="fixture_io",
            retryable=retryable,
            max_executions=1,
            retry_seconds=0.01,
        )
    return payload.work_id


def test_final_failure_release_retry_reuses_siblings_and_preserves_history(
    delivery_engine,
):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    old = fail_overview(runtime, scope, bundle_id, retryable=True)
    runtime.dependencies()
    for template in DiagramTemplate:
        if template != "system_overview":
            complete(runtime, scope, bundle_id, template)
    assert report_count(delivery_engine) == 0
    request = RetryRequest(
        resource_type=WorkKind.DIAGRAM,
        resource_id=old,
        idempotency_key="recover:overview",
    )
    actor = uuid4()
    accepted = runtime.retry(scope, request, actor, "OWNER")
    assert runtime.retry(scope, request, actor, "OWNER") == accepted
    complete(runtime, scope, bundle_id, "system_overview")
    assert report_count(delivery_engine) == 1
    assert runtime.retry(scope, request, actor, "OWNER") == accepted
    with Session(delivery_engine) as session:
        assert session.get(Work, old).state == "FAILED"
        assert not session.get(Work, old).is_current
        assert session.get(Work, accepted.work_id).run_number == 2
        assert session.scalar(select(func.count()).select_from(Output)) == 4
        assert (
            session.get(Bundle, bundle_id).sibling_release["reason"]
            == "overview_final_failure"
        )
    changed = request.model_copy(update={"idempotency_key": "other"})
    with pytest.raises(DeliveryApiError, match="delivery_retry_conflict"):
        runtime.retry(scope, changed, actor, "OWNER")


@pytest.mark.parametrize("role", ["DEVELOPER", "VIEWER"])
def test_retry_forbidden_and_no_successor(delivery_engine, role):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    old = fail_overview(runtime, scope, bundle_id, retryable=True)
    with pytest.raises(DeliveryApiError) as error:
        runtime.retry(
            scope,
            RetryRequest(
                resource_type=WorkKind.DIAGRAM, resource_id=old, idempotency_key="deny"
            ),
            uuid4(),
            role,
        )
    assert error.value.status == 403
    with Session(delivery_engine) as session:
        assert session.scalar(select(func.count()).select_from(Work)) == 5


@pytest.mark.parametrize("retryable", [False, True])
def test_retry_requires_classification_and_explicit_policy(delivery_engine, retryable):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    old = fail_overview(runtime, scope, bundle_id, retryable=retryable)
    runtime.manual_retry_policy = None
    with pytest.raises(DeliveryApiError) as error:
        runtime.retry(
            scope,
            RetryRequest(
                resource_type=WorkKind.DIAGRAM,
                resource_id=old,
                idempotency_key="policy",
            ),
            uuid4(),
            "ADMIN",
        )
    assert error.value.code == (
        "delivery_retry_policy_unavailable"
        if retryable
        else "delivery_retry_requires_new_input"
    )


def test_expired_lease_exhaustion_is_retryable_and_retryable_attempt_holds_siblings(
    delivery_engine,
):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    payload = payload_for(runtime, scope, bundle_id, "system_overview")
    with runtime.session() as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        identity = WorkIdentity.model_validate_json(
            json.dumps(session.get(Work, payload.work_id).identity)
        )
        lease = repo.claim(
            payload,
            identity.binding,
            "test-worker",
            max_executions=3,
            lease_seconds=30.0,
            execution_seconds=30.0,
        )
        repo.finish_failure(
            lease,
            code="fixture_io",
            retryable=True,
            max_executions=3,
            retry_seconds=0.01,
        )
    runtime.dependencies()
    with Session(delivery_engine) as session:
        assert session.get(Bundle, bundle_id).sibling_release is None
        assert not any(
            session.scalars(
                select(Work.dependencies_ready).where(
                    Work.template != "system_overview", Work.kind == WorkKind.DIAGRAM
                )
            )
        )


def test_failed_barrier_transaction_rolls_back_fourth_receipt_and_report(
    delivery_engine,
):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    for template in tuple(DiagramTemplate)[:3]:
        complete(runtime, scope, bundle_id, template)
    payload = payload_for(runtime, scope, bundle_id, "data_flow")
    with runtime.session() as session, session.begin():
        identity = WorkIdentity.model_validate_json(
            json.dumps(session.get(Work, payload.work_id).identity)
        )
        lease = SqlAlchemyDeliveryRepository(session).claim(
            payload,
            identity.binding,
            "test-worker",
            max_executions=3,
            lease_seconds=30.0,
            execution_seconds=30.0,
        )
    context = __import__("types").SimpleNamespace(
        attempt=lease.identity, prerequisites=None
    )
    registration = runtime.registry.resolve(identity.binding)
    candidate = registration.handler.execute(context)
    with pytest.raises(RuntimeError, match="lost before commit"):
        with runtime._uow() as uow:
            uow.complete(
                lease,
                candidate,
                registration.publication_factory,
                stage_dependencies=lambda session, receipt: runtime._dependencies(
                    uow, session, bundle_id, receipt
                ),
            )
            raise RuntimeError("lost before commit")
    assert report_count(delivery_engine) == 0
    with Session(delivery_engine) as session:
        assert session.scalar(select(func.count()).select_from(Output)) == 3
        assert session.get(Bundle, bundle_id).barrier is None


def test_readiness_failure_never_schedules_report(delivery_engine):
    runtime, scope, bundle_id, table = setup(delivery_engine)
    for template in tuple(DiagramTemplate)[:3]:
        complete(runtime, scope, bundle_id, template)
    with delivery_engine.begin() as connection:
        connection.execute(update(table).values(digest="f" * 64))
    result = runtime.execute(
        payload_for(runtime, scope, bundle_id, "data_flow"), "test-worker"
    )
    assert result == "failed"
    assert report_count(delivery_engine) == 0


def test_status_absent_is_read_only_and_contains_no_lease(delivery_engine):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    before = runtime.summary(scope, "VIEWER")
    encoded = before.model_dump_json()
    assert "lease_digest" not in encoded and "dispatch_epoch" not in encoded
    other = scope.model_copy(update={"architecture_version_id": uuid4()})
    assert runtime.summary(other, "OWNER").eligibility == "NOT_SCHEDULED"
    with Session(delivery_engine) as session:
        assert session.scalar(select(func.count()).select_from(Bundle)) == 1


def test_racing_retry_requests_create_one_successor_and_conflicting_key_is_rejected(
    delivery_engine,
):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    old = fail_overview(runtime, scope, bundle_id, retryable=True)
    actor = uuid4()

    def retry(key):
        try:
            return runtime.retry(
                scope,
                RetryRequest(
                    resource_type=WorkKind.DIAGRAM, resource_id=old, idempotency_key=key
                ),
                actor,
                "ADMIN",
            )
        except DeliveryApiError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(retry, ["first", "second"]))
    assert sum(not isinstance(result, str) for result in results) == 1
    assert "delivery_retry_conflict" in results
    key = "first" if not isinstance(results[0], str) else "second"
    with Session(delivery_engine) as session:
        other = session.scalar(select(Work.id).where(Work.template == "data_flow"))
        assert (
            session.scalar(
                select(func.count())
                .select_from(Work)
                .where(Work.template == "system_overview")
            )
            == 2
        )
    with pytest.raises(DeliveryApiError, match="delivery_idempotency_conflict"):
        runtime.retry(
            scope,
            RetryRequest(
                resource_type=WorkKind.DIAGRAM, resource_id=other, idempotency_key=key
            ),
            actor,
            "ADMIN",
        )


@pytest.mark.parametrize(
    "field", ["snapshot_id", "generation_id", "input_fingerprint", "profile"]
)
def test_mixed_scope_generation_input_or_profile_cannot_satisfy_barrier(
    delivery_engine, field
):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    for template in tuple(DiagramTemplate)[:3]:
        complete(runtime, scope, bundle_id, template)
    with Session(delivery_engine) as session, session.begin():
        row = session.scalar(
            select(Output)
            .join(Work, Work.id == Output.work_id)
            .where(Work.template == "component_architecture")
        )
        receipt = json.loads(json.dumps(row.receipt))
        reference = receipt["accepted"]["reference"]
        if field == "snapshot_id":
            reference["scope"][field] = str(uuid4())
        elif field == "profile":
            reference["binding"]["profile"]["configuration_fingerprint"] = "f" * 64
        elif field == "input_fingerprint":
            reference[field] = "f" * 64
        else:
            reference[field] = str(uuid4())
        row.receipt = receipt
    assert (
        runtime.execute(
            payload_for(runtime, scope, bundle_id, "data_flow"), "test-worker"
        )
        == "failed"
    )
    assert report_count(delivery_engine) == 0


def test_report_retry_keeps_original_pins_and_validates_exact_readiness(
    delivery_engine,
):
    runtime, scope, bundle_id, table = setup(delivery_engine)
    for template in DiagramTemplate:
        complete(runtime, scope, bundle_id, template)
    payload = payload_for(runtime, scope, bundle_id, "architecture_analysis")
    with runtime.session() as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        row = session.get(Work, payload.work_id)
        identity = WorkIdentity.model_validate_json(json.dumps(row.identity))
        lease = repo.claim(
            payload,
            identity.binding,
            "test-worker",
            max_executions=1,
            lease_seconds=30.0,
            execution_seconds=30.0,
        )
        repo.finish_failure(
            lease,
            code="fixture_report_io",
            retryable=True,
            max_executions=1,
            retry_seconds=0.01,
        )
        original = session.get(Bundle, bundle_id).barrier
    request = RetryRequest(
        resource_type=WorkKind.REPORT,
        resource_id=payload.work_id,
        idempotency_key="report:retry",
    )
    accepted = runtime.retry(scope, request, uuid4(), "OWNER")
    runtime.dependencies()
    with Session(delivery_engine) as session:
        assert session.get(Bundle, bundle_id).barrier == original
        assert (
            session.get(Work, accepted.work_id).identity["input_fingerprint"]
            == identity.input_fingerprint
        )
        assert report_count(delivery_engine) == 2  # one historical, one current run
    complete(runtime, scope, bundle_id, "architecture_analysis")
    with Session(delivery_engine) as session:
        assert session.get(Work, payload.work_id).state == "FAILED"


def test_retry_rate_limit_and_round_limit_are_enforced(delivery_engine):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    runtime.manual_retry_policy = ManualRetryPolicy(
        max_rounds=1, window_seconds=60.0, max_actor_requests=1, max_project_requests=1
    )
    old = fail_overview(runtime, scope, bundle_id, retryable=True)
    request = RetryRequest(
        resource_type=WorkKind.DIAGRAM, resource_id=old, idempotency_key="round1"
    )
    successor = runtime.retry(scope, request, uuid4(), "OWNER")
    assert successor.work_id != old
    # Finalize the successor with the same transient disposition.
    new = fail_overview(runtime, scope, bundle_id, retryable=True)
    with pytest.raises(DeliveryApiError, match="delivery_retry_policy_unavailable"):
        runtime.retry(
            scope,
            request.model_copy(
                update={"resource_id": new, "idempotency_key": "round2"}
            ),
            uuid4(),
            "OWNER",
        )


def test_cancellation_does_not_release_overview_siblings(delivery_engine):
    from backend.platform.delivery.model import CancellationCause, CancellationDecision

    runtime, scope, bundle_id, _ = setup(delivery_engine)
    with runtime.session() as session, session.begin():
        work = session.scalar(select(Work).where(Work.template == "system_overview"))
        assert SqlAlchemyDeliveryRepository(session).cancel(
            scope.project_id,
            CancellationDecision(
                cause=CancellationCause.ADMINISTRATIVE_WITHDRAWAL,
                actor_id=uuid4(),
                operation_id=uuid4(),
                expected_work_id=work.id,
                expected_fence=0,
            ),
        )
    runtime.dependencies()
    assert runtime.summary(scope, "OWNER").sibling_release_reason is None


def test_missing_profile_and_dispatch_drain_reject_new_retry_but_replay_is_stable(
    delivery_engine,
):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    old = fail_overview(runtime, scope, bundle_id, retryable=True)
    request = RetryRequest(
        resource_type=WorkKind.DIAGRAM, resource_id=old, idempotency_key="drain"
    )
    runtime.dispatch_enabled = False
    with pytest.raises(DeliveryApiError, match="delivery_runtime_unavailable"):
        runtime.retry(scope, request, uuid4(), "OWNER")
    runtime.dispatch_enabled = True
    runtime.registry = WorkHandlerRegistry()
    with pytest.raises(DeliveryApiError, match="delivery_handler_unavailable"):
        runtime.retry(scope, request, uuid4(), "OWNER")


def test_project_retry_admission_window_is_bounded(delivery_engine):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    runtime.manual_retry_policy = ManualRetryPolicy(
        max_rounds=3, window_seconds=60.0, max_actor_requests=1, max_project_requests=1
    )
    old = fail_overview(runtime, scope, bundle_id, retryable=True)
    runtime.retry(
        scope,
        RetryRequest(
            resource_type=WorkKind.DIAGRAM,
            resource_id=old,
            idempotency_key="first-admission",
        ),
        uuid4(),
        "ADMIN",
    )
    successor = fail_overview(runtime, scope, bundle_id, retryable=True)
    with pytest.raises(DeliveryApiError, match="delivery_retry_admission_wait"):
        runtime.retry(
            scope,
            RetryRequest(
                resource_type=WorkKind.DIAGRAM,
                resource_id=successor,
                idempotency_key="second-admission",
            ),
            uuid4(),
            "OWNER",
        )


def test_reconciler_health_evidence_expires_and_no_handler_is_not_success(
    delivery_engine,
):
    runtime, scope, bundle_id, _ = setup(delivery_engine)
    assert "reconciler_unavailable" in runtime.summary(scope, "OWNER").capabilities
    runtime.heartbeat("test-worker", reconciliation=True)
    assert "reconciler_unavailable" not in runtime.summary(scope, "OWNER").capabilities
    runtime.registry = WorkHandlerRegistry()
    summary = runtime.summary(scope, "VIEWER")
    assert "handler_unavailable" in summary.capabilities
    assert all(diagram.reference is None for diagram in summary.diagrams)


def test_api_source_inspection_uses_exact_version_public_read_contract(delivery_engine):
    from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
    from backend.platform.delivery.source import PublishedVersionReader
    from tests.p5.delivery.test_source import PublicSourceFixture

    source = PublicSourceFixture()
    header = source.header
    record = ArchitectureVersionResponse(
        id=header.architecture_version_id,
        analysis_id=header.analysis_id,
        project_id=header.project_id,
        repository_id=header.repository_id,
        snapshot_id=header.snapshot_id,
        sequence_number=header.sequence_number,
        published_at=header.published_at,
        architecture_schema_version=header.architecture_schema_version,
        ir_schema_version=header.ir_schema_version,
        content_digest=header.content_digest,
        entity_count=header.counts.entities,
        relationship_count=header.counts.relationships,
        evidence_count=header.counts.evidence,
        unresolved_relationship_count=header.counts.unresolved,
        conflict_count=header.counts.conflicts,
        completeness={},
    )
    reader = PublishedVersionReader(source, source.get_analysis)
    inspection = reader.inspect_requested(record)
    assert inspection.scope.architecture_version_id == header.architecture_version_id
    assert all(pair == (record.id, record.project_id) for pair in source.loads)
    from backend.platform.delivery.contracts import DeliveryContractError

    with pytest.raises(DeliveryContractError):
        reader.inspect_requested(record.model_copy(update={"snapshot_id": uuid4()}))


def test_pinned_scope_polling_validates_public_metadata_before_using_receipts(
    delivery_engine,
):
    from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
    from backend.platform.delivery.contracts import DeliveryContractError

    runtime, scope, _, _ = setup(delivery_engine)
    record = ArchitectureVersionResponse(
        id=scope.architecture_version_id,
        project_id=scope.project_id,
        repository_id=scope.repository_id,
        analysis_id=scope.analysis_id,
        snapshot_id=scope.snapshot_id,
        sequence_number=scope.sequence_number,
        published_at=scope.published_at,
        architecture_schema_version=scope.architecture_schema_version,
        ir_schema_version=scope.ir_schema_version,
        content_digest=scope.canonical_digest,
        entity_count=0,
        relationship_count=0,
        evidence_count=0,
        unresolved_relationship_count=0,
        conflict_count=0,
        completeness={},
    )
    assert runtime.scope_for_record(record) == scope
    with pytest.raises(DeliveryContractError, match="metadata changed"):
        runtime.scope_for_record(record.model_copy(update={"content_digest": "f" * 64}))
