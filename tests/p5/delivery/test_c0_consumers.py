"""Executable C0 obligations, NOT implementations of future producer storage.

Each producer must port these cases to its real store/index and public readers.
The memory fixture cannot prove filesystem/object-store/Elasticsearch durability.
"""

import hashlib
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.platform.delivery.contracts import (
    AcceptedOutput,
    AttemptRetirement,
    BarrierReceipt,
    CandidateSeal,
    DeliveryContractError,
    DiagramTemplate,
    OutputDigests,
    PreparedOutput,
    PublicationReceipt,
    WorkExecutionContext,
    WorkKind,
    execution_control,
)
from tests.p5.delivery.test_contracts import attempt, binding, receipt


class SealedGenerationFixture:
    """Producer contract double: private -> sealed -> committed or cleanup-marked.

    Candidate serialization/exclusion is producer-owned. M1 retirement alone is
    never accepted as deletion authority. No aliases, real I/O or storage engine.
    """

    def __init__(self, owner):
        self.owner, self.lock = owner, Lock()
        self.data, self.sealed, self.deleting = b"", False, False
        self.accepted, self.pins = None, set()
        self.prepared = None

    def write(self, data):
        with self.lock:
            if self.sealed or self.deleting:
                raise DeliveryContractError("generation is immutable or deleting")
            self.data = data

    def prepare(self):
        with self.lock:
            if self.prepared is not None:
                return self.prepared
            self.sealed = True
            digests = OutputDigests(
                content=hashlib.sha256(self.data).hexdigest(),
                spec=(
                    "a" * 64
                    if self.owner.work.binding.slot.kind == WorkKind.DIAGRAM
                    else None
                ),
                layout=(
                    "b" * 64
                    if self.owner.work.binding.slot.kind == WorkKind.DIAGRAM
                    else None
                ),
            )
            self.prepared = PreparedOutput(
                attempt=self.owner,
                candidate=CandidateSeal(
                    generation_id=uuid4(),
                    artifact_id=uuid4(),
                    size_bytes=len(self.data),
                    digests=digests,
                    sealed=True,
                ),
            )
            return self.prepared

    def accept(self, candidate):
        candidate.require_binding(self.owner)
        with self.lock:
            if (
                not self.sealed
                or self.deleting
                or len(self.data) != candidate.candidate.size_bytes
                or hashlib.sha256(self.data).hexdigest()
                != candidate.candidate.digests.content
            ):
                raise DeliveryContractError(
                    "publication cannot accept deleted/unsealed/corrupt candidate"
                )
            if self.accepted is not None:
                self.accepted.accepted.require_candidate(candidate)
                return self.accepted
            item = receipt(self.owner)
            from backend.platform.delivery.contracts import ArtifactReference

            reference = ArtifactReference(
                scope=self.owner.work.scope,
                binding=self.owner.work.binding,
                input_fingerprint=self.owner.work.input_fingerprint,
                resource_id=item.accepted.reference.resource_id,
                candidate_id=self.owner.candidate_id,
                generation_id=candidate.candidate.generation_id,
                artifact_id=candidate.candidate.artifact_id,
                digests=candidate.candidate.digests,
                size_bytes=candidate.candidate.size_bytes,
                sealed=True,
            )
            self.accepted = PublicationReceipt(
                receipt_id=uuid4(),
                prepared=candidate,
                accepted=AcceptedOutput(reference=reference),
            )
            return self.accepted

    def read_exact(self, reference, scope):
        with self.lock:
            if (
                self.accepted is None
                or reference != self.accepted.accepted.reference
                or reference.scope != scope
            ):
                raise DeliveryContractError("no committed exact reference")
            if (
                len(self.data) != reference.size_bytes
                or hashlib.sha256(self.data).hexdigest() != reference.digests.content
            ):
                raise DeliveryContractError("accepted artifact integrity failure")
            return self.data

    def mark_cleanup(self, retirement, *, grace_elapsed):
        with self.lock:
            if (
                retirement is None
                or retirement.attempt != self.owner
                or retirement.publication is not None
                or self.accepted is not None
                or self.pins
                or not grace_elapsed
            ):
                raise DeliveryContractError("cleanup exclusion not established")
            self.deleting = True


@pytest.mark.parametrize(
    "selected",
    [
        binding(),
        binding(WorkKind.DIAGRAM, DiagramTemplate.OVERVIEW),
        binding(WorkKind.REPORT),
    ],
)
def test_m2_m4_m5_sealing_and_m3_m6_exact_reference_consumers(selected):
    owner = attempt(selected)
    store = SealedGenerationFixture(owner)
    store.write(b"immutable producer-owned envelope")
    candidate = store.prepare()
    with pytest.raises(DeliveryContractError):
        store.write(b"late write")
    # A PreparedOutput is not a committed/published read capability.
    with pytest.raises(DeliveryContractError):
        store.read_exact(receipt(owner).accepted.reference, owner.work.scope)
    accepted = store.accept(candidate)
    assert store.read_exact(accepted.accepted.reference, owner.work.scope) == store.data
    alternate = accepted.accepted.reference.model_copy(
        update={"generation_id": uuid4()}
    )
    with pytest.raises(DeliveryContractError):
        store.read_exact(alternate, owner.work.scope)
    with pytest.raises(DeliveryContractError):
        store.read_exact(
            accepted.accepted.reference,
            owner.work.scope.model_copy(update={"project_id": uuid4()}),
        )
    # Simulated external loss/corruption fails, never selects another generation.
    store.data = b"corruption"
    with pytest.raises(DeliveryContractError, match="integrity"):
        store.read_exact(accepted.accepted.reference, owner.work.scope)


def test_retirement_grace_historical_pins_and_publication_cleanup_exclusion():
    owner = attempt()
    store = SealedGenerationFixture(owner)
    store.write(b"candidate")
    prepared = store.prepare()
    retired = AttemptRetirement(
        attempt=owner, outcome="EXPIRED", ended_at=datetime.now(UTC)
    )
    with pytest.raises(DeliveryContractError):
        store.mark_cleanup(None, grace_elapsed=True)
    with pytest.raises(DeliveryContractError):
        store.mark_cleanup(retired, grace_elapsed=False)
    store.pins.add("historical-report-reference")
    with pytest.raises(DeliveryContractError):
        store.mark_cleanup(retired, grace_elapsed=True)
    store.pins.clear()
    store.mark_cleanup(retired, grace_elapsed=True)
    store.mark_cleanup(retired, grace_elapsed=True)  # Idempotent crash recovery.
    with pytest.raises(DeliveryContractError):
        store.accept(prepared)
    other = SealedGenerationFixture(owner)
    other.write(b"published")
    accepted = other.accept(other.prepare())
    completed = AttemptRetirement(
        attempt=owner,
        outcome="COMPLETED",
        ended_at=datetime.now(UTC),
        publication=accepted,
    )
    with pytest.raises(DeliveryContractError):
        other.mark_cleanup(completed, grace_elapsed=True)


def test_report_prerequisites_are_exact_and_report_only():
    owner = attempt(binding(WorkKind.REPORT))
    kwargs = dict(
        attempt=owner,
        deadline=datetime.now(UTC),
        control=execution_control(lambda: None),
    )
    with pytest.raises(ValidationError):
        WorkExecutionContext(**kwargs)
    barrier = BarrierReceipt(
        scope=owner.work.scope,
        report_profile=owner.work.binding.profile,
        diagrams=tuple(
            receipt(
                attempt(
                    binding(WorkKind.DIAGRAM, t), owner.work.scope, owner.work.bundle_id
                )
            )
            for t in DiagramTemplate
        ),
    )
    owner = owner.model_copy(
        update={
            "work": owner.work.model_copy(
                update={"input_fingerprint": barrier.input_fingerprint()}
            )
        }
    )
    assert (
        WorkExecutionContext(
            **{**kwargs, "attempt": owner}, prerequisites=barrier
        ).prerequisites
        == barrier
    )
    with pytest.raises(ValidationError):
        WorkExecutionContext(**{**kwargs, "attempt": attempt()}, prerequisites=barrier)


@pytest.mark.parametrize("corruption", ["seal", "version", "profile"])
def test_unchecked_producer_values_rejected_at_execute_boundary(corruption):
    from backend.platform.delivery.registry import (
        HandlerRegistration,
        WorkHandlerRegistry,
    )

    item = receipt()
    candidate = item.prepared
    if corruption == "seal":
        candidate = candidate.model_copy(
            update={
                "candidate": candidate.candidate.model_copy(update={"sealed": False})
            }
        )
    elif corruption == "version":
        candidate = candidate.model_copy(update={"contract_version": "2.0.0"})
    else:
        owner = candidate.attempt
        candidate = candidate.model_copy(
            update={
                "attempt": owner.model_copy(
                    update={
                        "work": owner.work.model_copy(
                            update={
                                "binding": owner.work.binding.model_copy(
                                    update={"contract_version": "unsupported"}
                                )
                            }
                        )
                    }
                )
            }
        )

    class Producer:
        def execute(self, context):
            return candidate

    registry = WorkHandlerRegistry(
        (
            HandlerRegistration(
                item.prepared.attempt.work.binding, Producer(), lambda session: None
            ),
        )
    )
    context = WorkExecutionContext(
        attempt=item.prepared.attempt,
        deadline=datetime.now(UTC),
        control=execution_control(lambda: None),
    )
    with pytest.raises(ValidationError):
        registry.execute(context)


def test_live_publication_context_and_historical_read_context_bind_same_exact_owner():
    from backend.platform.delivery.publication import (
        PublicationContext,
        PublicationContractViolation,
    )

    item = receipt()
    context = PublicationContext(
        transaction_id=uuid4(),
        attempt=item.prepared.attempt,
        deadline=datetime.now(UTC),
    )
    context.require_prepared(item.prepared)
    context.require_reference(item.accepted.reference)
    with pytest.raises(PublicationContractViolation):
        context.require_reference(
            item.accepted.reference.model_copy(update={"candidate_id": uuid4()})
        )
    with pytest.raises(ValidationError):
        context.model_copy(update={"contract_version": "2.0.0"}).require_reference(
            item.accepted.reference
        )


def test_runtime_binding_required_without_silent_candidate_upgrade():
    from backend.platform.delivery.contracts import DeliveryPolicy
    from tests.p5.integration.test_delivery_postgres import policy

    value = policy().model_dump()
    value.pop("execution_policy_fingerprint")
    with pytest.raises(ValidationError):
        DeliveryPolicy.model_validate(value)


def test_four_templates_cannot_relabel_one_execution_as_multiple_prerequisites():
    owner = attempt(binding(WorkKind.REPORT))
    shared_attempt = uuid4()
    items = tuple(
        receipt(
            attempt(
                binding(WorkKind.DIAGRAM, template),
                owner.work.scope,
                owner.work.bundle_id,
            ).model_copy(update={"attempt_id": shared_attempt})
        )
        for template in DiagramTemplate
    )
    with pytest.raises(ValidationError):
        BarrierReceipt(
            scope=owner.work.scope,
            report_profile=owner.work.binding.profile,
            diagrams=items,
        )


def test_retry_request_is_immutable_and_unsupported_overrides_fail_validation():
    from backend.platform.delivery.api_contracts import RetryRequest

    request = RetryRequest(
        resource_type=WorkKind.SEARCH, resource_id=uuid4(), idempotency_key="c0:retry"
    )
    with pytest.raises(ValidationError):
        request.idempotency_key = "changed"
    with pytest.raises(ValidationError):
        RetryRequest.model_validate(
            request.model_copy(update={"resource_type": "arbitrary"})
        )


@pytest.mark.parametrize("value", [1, "true", False])
def test_seal_is_a_literal_boolean_not_coerced_data(value):
    from backend.platform.delivery.contracts import ArtifactReference, CandidateSeal

    item = receipt()
    with pytest.raises(ValidationError):
        CandidateSeal.model_validate(
            {**item.prepared.candidate.model_dump(), "sealed": value}
        )
    with pytest.raises(ValidationError):
        ArtifactReference.model_validate(
            {**item.accepted.reference.model_dump(), "sealed": value}
        )


def test_cancellation_actor_classification_is_internal_audit_not_a_public_role():
    from backend.platform.delivery.model import CancellationCause, CancellationDecision

    kwargs = dict(
        cause=CancellationCause.ADMINISTRATIVE_WITHDRAWAL,
        actor_id=uuid4(),
        operation_id=uuid4(),
        expected_work_id=uuid4(),
        expected_fence=0,
    )
    assert CancellationDecision(**kwargs).actor_type == "operator"
    assert CancellationDecision(**kwargs, actor_type="system").actor_type == "system"
    with pytest.raises(DeliveryContractError):
        CancellationDecision(**kwargs, actor_type="OWNER")


def test_api_and_worker_share_public_registration_seam(monkeypatch):
    from sqlalchemy import create_engine

    from backend.platform.config import Settings
    from backend.platform.delivery import dependencies
    from backend.platform.delivery.registry import (
        HandlerRegistration,
        WorkHandlerRegistry,
    )
    from backend.platform.delivery.service import FleetManifest
    from tests.p5.delivery.test_registry import FixtureConsumer
    from tests.p5.delivery.test_rollout import budgets
    from tests.p5.integration.test_delivery_postgres import policy

    producer = FixtureConsumer(receipt())
    registry = WorkHandlerRegistry(
        (HandlerRegistration(binding(), producer, producer.factory),)
    )
    monkeypatch.setattr(dependencies, "get_delivery_handler_registry", lambda: registry)
    settings = Settings(
        delivery_dispatch_enabled=False,
        delivery_operational_approval=False,
        delivery_runtime_json=budgets().model_dump_json(),
        delivery_policy_json=policy().model_dump_json(),
        delivery_fleet_json=FleetManifest(
            queue="analysis.jobs",
            deployment_epoch="test",
            workers=("fixture",),
            admission_approved=True,
        ).model_dump_json(),
        analysis_queue_name="analysis.jobs",
    )
    engine = create_engine("postgresql+psycopg://unused/unused")  # Never connected.
    try:
        first = dependencies.build_delivery_coordinator(engine, settings, object())
        second = dependencies.build_delivery_coordinator(engine, settings, object())
        assert first.registry is second.registry is registry
        explicit = dependencies.build_delivery_coordinator(
            engine, settings, object(), registry=WorkHandlerRegistry()
        )
        assert explicit.registry.profiles == ()
    finally:
        engine.dispose()
