"""Consumer fixtures use public execution and enlisted-publication ports."""

from datetime import UTC, datetime

import pytest

from backend.platform.delivery.contracts import (
    BarrierReceipt,
    DeliveryContractError,
    DiagramTemplate,
    WorkExecutionContext,
    WorkKind,
    execution_control,
)
from backend.platform.delivery.publication import PublicationContext, ReadyValidation
from backend.platform.delivery.registry import (
    HandlerRegistration,
    HandlerUnavailable,
    WorkHandlerRegistry,
)
from tests.p5.delivery.test_contracts import attempt, binding, receipt


class FixtureConsumer:
    """No database, external storage, callbacks, tasks or success side effects."""

    def __init__(self, output):
        self.output = output

    def execute(self, context):
        context.control.checkpoint()
        self.output.prepared.require_binding(context.attempt)
        return self.output.prepared

    def publish_prepared(self, prepared, context):
        context.require_prepared(prepared)
        self.output.accepted.require_candidate(prepared)
        return self.output.accepted

    def validate_ready(self, reference, context):
        assert reference == self.output.accepted.reference
        return ReadyValidation(reference=reference)

    def factory(self, borrowed_session):
        # Production factory receives only the guarded borrowed Session.
        return self


@pytest.mark.parametrize(
    "selected",
    [
        binding(),
        binding(WorkKind.REPORT),
        *(binding(WorkKind.DIAGRAM, t) for t in DiagramTemplate),
    ],
)
def test_search_diagram_report_public_consumer_contract(selected) -> None:
    owner, prerequisites = attempt(selected), None
    if selected.slot.kind == WorkKind.REPORT:
        prerequisites = BarrierReceipt(
            scope=owner.work.scope,
            report_profile=selected.profile,
            diagrams=tuple(
                receipt(
                    attempt(
                        binding(WorkKind.DIAGRAM, template),
                        owner.work.scope,
                        owner.work.bundle_id,
                    )
                )
                for template in DiagramTemplate
            ),
        )
        owner = type(owner).model_validate(
            {
                **owner.model_dump(),
                "work": {
                    **owner.work.model_dump(),
                    "input_fingerprint": prerequisites.input_fingerprint(),
                },
            }
        )
    item = receipt(owner)
    producer = FixtureConsumer(item)
    registration = HandlerRegistration(selected, producer, producer.factory)
    registry = WorkHandlerRegistry((registration,))
    found = registry.resolve(selected)
    context = WorkExecutionContext(
        attempt=item.prepared.attempt,
        deadline=datetime.now(UTC),
        control=execution_control(lambda: None),
        prerequisites=prerequisites,
    )
    assert found is registration
    prepared = registry.execute(context)
    pub = PublicationContext(
        transaction_id=item.receipt_id,
        attempt=context.attempt,
        deadline=context.deadline,
    )
    accepted = producer.publish_prepared(prepared, pub)
    accepted.require_candidate(prepared)
    assert (
        producer.validate_ready(accepted.reference, pub).reference == accepted.reference
    )
    assert registry.profiles == (selected,)
    # No committed READY assertion: B2 must prove the real outer transaction.


def test_missing_duplicate_and_wrong_version_never_fall_back() -> None:
    item = receipt()
    producer = FixtureConsumer(item)
    selected = item.prepared.attempt.work.binding
    entry = HandlerRegistration(selected, producer, producer.factory)
    with pytest.raises(DeliveryContractError):
        WorkHandlerRegistry((entry, entry))
    with pytest.raises(HandlerUnavailable):
        WorkHandlerRegistry().resolve(selected)
    profile = selected.profile.model_copy(update={"generator_version": "2.0.0"})
    with pytest.raises(HandlerUnavailable):
        WorkHandlerRegistry((entry,)).resolve(
            selected.model_copy(update={"profile": profile})
        )


def test_wrong_attempt_handler_output_is_rejected_before_publication() -> None:
    item = receipt()
    producer = FixtureConsumer(item)
    # A broken producer ignores both binding and cooperative checks.
    producer.execute = lambda context: item.prepared
    selected = item.prepared.attempt.work.binding
    registry = WorkHandlerRegistry(
        (HandlerRegistration(selected, producer, producer.factory),)
    )
    context = WorkExecutionContext(
        attempt=attempt(selected),
        deadline=datetime.now(UTC),
        control=execution_control(lambda: None),
    )
    with pytest.raises(DeliveryContractError):
        registry.execute(context)


def test_multiple_pinned_versions_coexist_without_latest_fallback() -> None:
    first = receipt()
    selected = first.prepared.attempt.work.binding
    second_binding = selected.model_copy(
        update={
            "profile": selected.profile.model_copy(
                update={"generator_version": "2.0.0"}
            )
        }
    )
    second = receipt(attempt(second_binding))
    old, new = FixtureConsumer(first), FixtureConsumer(second)
    entries = (
        HandlerRegistration(selected, old, old.factory),
        HandlerRegistration(second_binding, new, new.factory),
    )
    registry = WorkHandlerRegistry(entries)
    assert registry.resolve(selected).handler is old
    assert registry.resolve(second_binding).handler is new
    assert WorkHandlerRegistry(tuple(reversed(entries))).profiles == registry.profiles
