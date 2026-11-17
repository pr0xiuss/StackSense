"""C0 consumers use exact identities; a DTO is not a storage/commit proof."""

from datetime import UTC, datetime, timedelta
from itertools import permutations
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.platform.delivery.contracts import (
    AcceptedOutput,
    ArtifactReference,
    AttemptIdentity,
    BarrierReceipt,
    CandidateSeal,
    DeliveryContractError,
    DeliveryPolicy,
    DeliveryWorkPayload,
    DependencyReceipt,
    DiagramTemplate,
    HandlerProfile,
    OutputDigests,
    PreparedOutput,
    ProducerProfile,
    PublicationReceipt,
    VersionScope,
    WorkIdentity,
    WorkKind,
    WorkSlot,
    bundle_fingerprint,
    fingerprint,
    work_fingerprint,
)


def scope() -> VersionScope:
    return VersionScope(
        project_id=uuid4(),
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=uuid4(),
        sequence_number=1,
        published_at=datetime.now(UTC),
        canonical_digest="a" * 64,
        source_contract_version="1.0.0",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        configuration_fingerprint="frozen-source-profile",
    )


def binding(
    kind: WorkKind = WorkKind.SEARCH, template: DiagramTemplate | None = None
) -> HandlerProfile:
    return HandlerProfile(
        slot=WorkSlot(
            kind=kind,
            template="architecture_analysis" if kind == WorkKind.REPORT else template,
        ),
        profile=ProducerProfile(
            producer_id="fixture",
            producer_version="1.0.0",
            generator_version="1.0.0",
            output_schema_version="1.0.0",
            configuration_fingerprint="b" * 64,
        ),
    )


def attempt(
    selected: HandlerProfile | None = None,
    selected_scope: VersionScope | None = None,
    bundle_id: object = None,
) -> AttemptIdentity:
    return AttemptIdentity(
        work=WorkIdentity(
            scope=selected_scope or scope(),
            bundle_id=bundle_id or uuid4(),
            work_id=uuid4(),
            run_number=1,
            binding=selected or binding(),
            bundle_fingerprint="b" * 64,
            input_fingerprint="c" * 64,
        ),
        attempt_id=uuid4(),
        ordinal=1,
        fence=1,
        dispatch_epoch=uuid4(),
        candidate_id=uuid4(),
    )


def receipt(identity: AttemptIdentity | None = None) -> PublicationReceipt:
    owner = identity or attempt()
    diagram = owner.work.binding.slot.kind == WorkKind.DIAGRAM
    digests = OutputDigests(
        content="d" * 64,
        spec="e" * 64 if diagram else None,
        layout="f" * 64 if diagram else None,
    )
    candidate = CandidateSeal(
        generation_id=uuid4(),
        artifact_id=uuid4(),
        size_bytes=17,
        digests=digests,
        sealed=True,
    )
    prepared = PreparedOutput(attempt=owner, candidate=candidate)
    ref = ArtifactReference(
        scope=owner.work.scope,
        binding=owner.work.binding,
        input_fingerprint=owner.work.input_fingerprint,
        resource_id=uuid4(),
        candidate_id=owner.candidate_id,
        generation_id=candidate.generation_id,
        artifact_id=candidate.artifact_id,
        size_bytes=17,
        digests=digests,
        sealed=True,
    )
    return PublicationReceipt(
        receipt_id=uuid4(), prepared=prepared, accepted=AcceptedOutput(reference=ref)
    )


def validated_change(value: object, **changes: object) -> object:
    # Test fixtures deliberately use validation, never unchecked model_copy.
    return type(value).model_validate({**value.model_dump(), **changes})  # type: ignore[attr-defined]


def test_exact_json_round_trip_immutability_and_timezone() -> None:
    item = receipt()
    assert PublicationReceipt.model_validate_json(item.model_dump_json()) == item
    with pytest.raises(ValidationError):
        item.prepared.attempt.fence = 9
    with pytest.raises(ValidationError):
        validated_change(
            item.prepared.attempt.work.scope, published_at=datetime(2026, 1, 1)
        )
    assert isinstance(item.prepared.attempt.work.scope.project_id, type(uuid4()))


@pytest.mark.parametrize(
    "field", ["attempt_id", "dispatch_epoch", "candidate_id", "fence", "ordinal"]
)
def test_prepared_rejects_successor_even_when_bytes_equal(field: str) -> None:
    item = receipt().prepared
    replacement = 2 if field in {"fence", "ordinal"} else uuid4()
    other = validated_change(item.attempt, **{field: replacement})
    with pytest.raises(DeliveryContractError):
        item.require_binding(other)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    [
        "bundle_id",
        "work_id",
        "run_number",
        "bundle_fingerprint",
        "input_fingerprint",
        "scope",
        "binding",
    ],
)
def test_prepared_rejects_every_work_binding_mismatch(field: str) -> None:
    prepared = receipt().prepared
    changes = {
        "bundle_id": uuid4(),
        "work_id": uuid4(),
        "run_number": 2,
        "bundle_fingerprint": "1" * 64,
        "input_fingerprint": "2" * 64,
        "scope": scope(),
        "binding": binding(WorkKind.REPORT),
    }
    work = validated_change(prepared.attempt.work, **{field: changes[field]})
    owner = validated_change(prepared.attempt, work=work)
    with pytest.raises(DeliveryContractError):
        prepared.require_binding(owner)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    [
        "producer_id",
        "producer_version",
        "generator_version",
        "output_schema_version",
        "configuration_fingerprint",
    ],
)
def test_prepared_rejects_each_profile_mismatch(field: str) -> None:
    prepared = receipt().prepared
    profile = validated_change(
        prepared.attempt.work.binding.profile,
        **{field: "9" * 64 if field.endswith("fingerprint") else "new"},
    )
    changed_binding = validated_change(prepared.attempt.work.binding, profile=profile)
    work = validated_change(prepared.attempt.work, binding=changed_binding)
    with pytest.raises(DeliveryContractError):
        prepared.require_binding(validated_change(prepared.attempt, work=work))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    [
        "generation_id",
        "artifact_id",
        "candidate_id",
        "input_fingerprint",
        "digests",
        "size_bytes",
    ],
)
def test_accepted_output_must_match_sealed_candidate(field: str) -> None:
    item = receipt()
    replacement = (
        18
        if field == "size_bytes"
        else (
            "3" * 64
            if field == "input_fingerprint"
            else OutputDigests(content="3" * 64) if field == "digests" else uuid4()
        )
    )
    ref = validated_change(item.accepted.reference, **{field: replacement})
    with pytest.raises(DeliveryContractError):
        AcceptedOutput(reference=ref).require_candidate(item.prepared)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"sealed": False},
        {"latest": True},
        {"generation_id": "latest"},
        {"size_bytes": -1},
        {"alias": "current"},
        {"storage_key": "/private/path"},
    ],
)
def test_mutable_or_invalid_reference_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        validated_change(receipt().accepted.reference, **changes)


def test_fingerprints_tagged_stable_unicode_and_strict_json() -> None:
    assert fingerprint("x", {"é": 1, "b": [2]}) == fingerprint("x", {"b": (2,), "é": 1})
    assert fingerprint("x", "abc") != fingerprint("y", "abc")
    for value in [
        float("nan"),
        float("inf"),
        {1: "bad"},
        {"bad": {1, 2}},
        "\ud800",
        b"bytes",
    ]:
        with pytest.raises(ValueError):
            fingerprint("x", value)


def test_policy_complete_order_independent_and_time_not_semantic() -> None:
    profiles = (
        binding(),
        binding(WorkKind.REPORT),
        *(binding(WorkKind.DIAGRAM, t) for t in DiagramTemplate),
    )
    policy = DeliveryPolicy(
        policy_version="v1", profiles=profiles, execution_policy_fingerprint="0" * 64
    )
    reverse = DeliveryPolicy(
        policy_version="v1",
        profiles=tuple(reversed(profiles)),
        execution_policy_fingerprint="0" * 64,
    )
    s = scope()
    assert bundle_fingerprint(s, policy) == bundle_fingerprint(s, reverse)
    changed_time = VersionScope.model_validate(
        {**s.model_dump(), "published_at": s.published_at + timedelta(seconds=1)}
    )
    assert bundle_fingerprint(s, policy) == bundle_fingerprint(changed_time, policy)
    assert work_fingerprint(
        bundle_fingerprint(s, policy), profiles[0]
    ) != work_fingerprint(bundle_fingerprint(s, policy), profiles[1])
    for invalid in [profiles[:-1], profiles + (profiles[0],)]:
        with pytest.raises(ValidationError):
            DeliveryPolicy(
                policy_version="v1",
                profiles=invalid,
                execution_policy_fingerprint="0" * 64,
            )


def test_four_reference_barrier_is_order_invariant_and_pins_report() -> None:
    s, bundle_id = scope(), uuid4()
    outputs = tuple(
        receipt(attempt(binding(WorkKind.DIAGRAM, t), s, bundle_id))
        for t in DiagramTemplate
    )
    first = BarrierReceipt(
        scope=s, report_profile=binding(WorkKind.REPORT).profile, diagrams=outputs
    )
    for order in permutations(outputs):
        assert (
            BarrierReceipt(
                scope=s, report_profile=first.report_profile, diagrams=order
            ).input_fingerprint()
            == first.input_fingerprint()
        )
    for invalid in [
        outputs[:3],
        outputs[:3] + (outputs[0],),
        outputs[:3]
        + (receipt(attempt(binding(WorkKind.DIAGRAM, DiagramTemplate.DATA_FLOW))),),
    ]:
        with pytest.raises(ValidationError):
            BarrierReceipt(
                scope=s, report_profile=first.report_profile, diagrams=invalid
            )


def test_search_and_report_consumers_use_same_public_receipt_shape() -> None:
    for kind in [WorkKind.SEARCH, WorkKind.REPORT]:
        item = receipt(attempt(binding(kind)))
        item.accepted.require_candidate(item.prepared)


def test_identifier_only_payload_unknown_version_scope_and_override_rejection() -> None:
    identity = attempt()
    data = dict(
        contract_version="1.0.0",
        work_id=identity.work.work_id,
        bundle_id=identity.work.bundle_id,
        project_id=identity.work.scope.project_id,
        architecture_version_id=identity.work.scope.architecture_version_id,
        dispatch_epoch=identity.dispatch_epoch,
        correlation_id="fixture:one",
    )
    payload = DeliveryWorkPayload(**data)
    payload.require_work(identity.work, identity.dispatch_epoch)
    assert DeliveryWorkPayload.model_validate_json(payload.model_dump_json()) == payload
    for changes in [
        {"profile": "latest"},
        {"lease_token": "secret"},
        {"contract_version": "2.0.0"},
        {"source": "code"},
        {"attempt_id": uuid4()},
    ]:
        with pytest.raises(ValidationError):
            DeliveryWorkPayload.model_validate({**data, **changes})
    with pytest.raises(ValidationError):
        DeliveryWorkPayload.model_validate(
            {k: v for k, v in data.items() if k != "contract_version"}
        )
    with pytest.raises(DeliveryContractError):
        payload.require_work(identity.work, uuid4())


def test_dependency_receipt_cannot_invent_ready_or_mix_scope() -> None:
    item = receipt()
    fields = dict(
        scope=item.accepted.reference.scope,
        prerequisite_work_id=item.prepared.attempt.work.work_id,
    )
    DependencyReceipt(**fields, reason="prerequisite_ready", output=item)
    DependencyReceipt(**fields, reason="overview_final_failure")
    with pytest.raises(ValidationError):
        DependencyReceipt(**fields, reason="prerequisite_ready")
    with pytest.raises(ValidationError):
        DependencyReceipt(**fields, reason="overview_final_failure", output=item)
    with pytest.raises(ValidationError):
        DependencyReceipt(
            **{**fields, "scope": scope()}, reason="prerequisite_ready", output=item
        )


def test_barrier_requires_all_pinned_policy_profiles_and_fingerprints() -> None:
    profiles = (
        binding(),
        binding(WorkKind.REPORT),
        *(binding(WorkKind.DIAGRAM, t) for t in DiagramTemplate),
    )
    policy = DeliveryPolicy(
        policy_version="v1", profiles=profiles, execution_policy_fingerprint="0" * 64
    )
    s, bundle_id = scope(), uuid4()
    bundle_hash = bundle_fingerprint(s, policy)
    outputs = []
    for selected in profiles:
        if selected.slot.kind != WorkKind.DIAGRAM:
            continue
        owner = attempt(selected, s, bundle_id)
        work = validated_change(
            owner.work,
            bundle_fingerprint=bundle_hash,
            input_fingerprint=work_fingerprint(bundle_hash, selected),
        )
        outputs.append(receipt(validated_change(owner, work=work)))
    barrier = BarrierReceipt(
        scope=s, report_profile=profiles[1].profile, diagrams=tuple(outputs)
    )
    barrier.require_policy(policy, bundle_id)
    with pytest.raises(DeliveryContractError):
        barrier.require_policy(policy, uuid4())
    changed = policy.model_copy(update={"policy_version": "v2"})
    with pytest.raises(DeliveryContractError):
        barrier.require_policy(changed, bundle_id)


def test_nested_unchecked_model_copy_cannot_bypass_contract_validation() -> None:
    item = receipt()
    corrupted = item.accepted.reference.model_copy(update={"sealed": False})
    with pytest.raises(ValidationError):
        AcceptedOutput(reference=corrupted)
