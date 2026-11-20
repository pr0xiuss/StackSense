"""Unit tests for P5-C3 ContextBuilder and deterministic semantic digest.

Adheres to §7A.8 and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.platform.knowledge.context import ContextBuilder
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    C3_CONTRACT_VERSION,
    CanonicalFactView,
    ConflictView,
    ContextBundle,
    Coverage,
    EvidenceItemView,
    FreshnessState,
    LimitsAndUsage,
    RelationshipView,
    ResolutionState,
    ResolvedSubject,
    RetrievalCapacityExceededError,
    RetrievalOperation,
    RetrievalOutcome,
    RetrievalPlan,
    RetrievalScope,
    SelectionRationale,
    SelectionRationaleCode,
    SourceKind,
    SourceObservation,
    SubjectSelector,
    UnresolvedView,
)


def _make_scope() -> RetrievalScope:
    return RetrievalScope(
        project_id=uuid4(),
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=uuid4(),
        sequence_number=1,
        canonical_digest="a" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        published_at=datetime.now(UTC),
    )


def _make_plan(policy: RetrievalPolicy | None = None) -> RetrievalPlan:
    return RetrievalPlan(
        strategy_version="1.0.0",
        request_fingerprint="b" * 64,
        operations=(
            RetrievalOperation.LOOKUP,
            RetrievalOperation.RELATIONSHIPS,
            RetrievalOperation.EVIDENCE,
        ),
        subjects=(SubjectSelector.from_logical_id("entity", "service_payment"),),
        required_sources=(SourceKind.CANONICAL,),
        optional_sources=(SourceKind.SEARCH, SourceKind.GRAPH),
        policy_fingerprint=(policy or RetrievalPolicy()).compute_fingerprint(),
        budget_snapshot={"limit": 25},
    )


def test_context_builder_happy_path():
    """Verify ContextBuilder builds a valid, frozen ContextBundle.

    Checks accurate limits, outcome, and frozen views.
    """
    scope = _make_scope()
    plan = _make_plan()
    policy = RetrievalPolicy()

    fact = CanonicalFactView(
        record_id=uuid4(),
        logical_id="service_payment",
        kind="service",
        name="PaymentService",
        status="confirmed",
        metadata={"tier": "critical"},
        evidence_references=("ev_1",),
    )
    rel = RelationshipView(
        record_id=uuid4(),
        logical_id="rel_payment_db",
        kind="connects_to",
        status="confirmed",
        source_logical_id="service_payment",
        target_logical_id="db_payment",
        evidence_references=("ev_1",),
    )
    ev = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_1",
        source_record_type="ast",
        path="src/payment.py",
        polarity="supporting",
        strength="direct_source",
        subject_references=("service_payment", "rel_payment_db"),
    )
    unres = UnresolvedView(
        record_id=uuid4(),
        logical_id="unres_1",
        reason="not_found",
        unresolved_type="missing_queue",
        source_logical_id="service_payment",
    )
    conf = ConflictView(
        record_id=uuid4(),
        logical_id="conf_1",
        conflict_type="competing_declaration",
        subject_key="service_payment",
    )
    rat = SelectionRationale(
        code=SelectionRationaleCode.EXPLICIT_IDENTITY,
        target_logical_id="service_payment",
        target_kind="service",
    )
    obs = SourceObservation(
        source_kind=SourceKind.CANONICAL,
        contract_version="1.0.0",
        generation_id=uuid4(),
    )
    subj = ResolvedSubject(
        selector=SubjectSelector.from_logical_id("entity", "service_payment"),
        state=ResolutionState.RESOLVED,
        selected_id=fact.record_id,
        selected_logical_id="service_payment",
        selected_kind="service",
    )

    builder = ContextBuilder(
        scope=scope,
        plan=plan.model_copy(
            update={"policy_fingerprint": policy.compute_fingerprint()}
        ),
        policy=policy,
    )
    bundle = builder.build_bundle(
        source_observations=[obs],
        resolved_subjects=[subj],
        facts=[fact],
        relationships=[rel],
        evidence=[ev],
        unresolved=[unres],
        conflicts=[conf],
        rationales=[rat],
    )

    assert bundle.c3_version == C3_CONTRACT_VERSION
    assert bundle.scope == scope
    assert bundle.outcome == RetrievalOutcome.COMPLETE
    assert len(bundle.facts) == 1
    assert len(bundle.relationships) == 1
    assert len(bundle.evidence) == 1
    assert len(bundle.unresolved) == 1
    assert len(bundle.conflicts) == 1
    assert len(bundle.rationales) == 1
    assert len(bundle.semantic_digest) == 64
    assert bundle.limits_and_usage.total_output_bytes > 0


def test_permutation_stability():
    """Verify that shuffling inputs produces an identical semantic digest.

    Also verifies ordered canonical views are deterministic.
    """
    scope = _make_scope()
    plan = _make_plan()
    policy = RetrievalPolicy()

    fact1 = CanonicalFactView(
        record_id=uuid4(),
        logical_id="ent_a",
        kind="service",
        name="ServiceA",
        status="confirmed",
    )
    fact2 = CanonicalFactView(
        record_id=uuid4(),
        logical_id="ent_b",
        kind="database",
        name="DatabaseB",
        status="confirmed",
    )
    rel1 = RelationshipView(
        record_id=uuid4(),
        logical_id="rel_1",
        kind="calls",
        status="confirmed",
        source_logical_id="ent_a",
        target_logical_id="ent_b",
    )
    rel2 = RelationshipView(
        record_id=uuid4(),
        logical_id="rel_2",
        kind="queries",
        status="confirmed",
        source_logical_id="ent_a",
        target_logical_id="ent_b",
    )
    ev1 = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_a",
        source_record_type="ast",
        path="src/a.py",
        polarity="supporting",
        strength="direct_source",
    )
    ev2 = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_b",
        source_record_type="ast",
        path="src/b.py",
        polarity="conflicting",
        strength="framework_structural",
    )
    rat1 = SelectionRationale(
        code=SelectionRationaleCode.EXPLICIT_IDENTITY,
        target_logical_id="ent_a",
        target_kind="service",
    )
    rat2 = SelectionRationale(
        code=SelectionRationaleCode.DIRECT_RELATIONSHIP,
        target_logical_id="ent_b",
        target_kind="database",
    )

    builder = ContextBuilder(
        scope=scope,
        plan=plan.model_copy(
            update={"policy_fingerprint": policy.compute_fingerprint()}
        ),
        policy=policy,
    )

    bundle1 = builder.build_bundle(
        facts=[fact1, fact2],
        relationships=[rel1, rel2],
        evidence=[ev1, ev2],
        rationales=[rat1, rat2],
    )

    # Reverse input orders
    bundle2 = builder.build_bundle(
        facts=[fact2, fact1],
        relationships=[rel2, rel1],
        evidence=[ev2, ev1],
        rationales=[rat2, rat1],
    )

    assert bundle1.semantic_digest == bundle2.semantic_digest
    assert [f.logical_id for f in bundle1.facts] == [
        f.logical_id for f in bundle2.facts
    ]
    assert [r.logical_id for r in bundle1.relationships] == [
        r.logical_id for r in bundle2.relationships
    ]
    assert [e.logical_id for e in bundle1.evidence] == [
        e.logical_id for e in bundle2.evidence
    ]
    assert [r.code.value for r in bundle1.rationales] == [
        r.code.value for r in bundle2.rationales
    ]


def test_semantic_digest_invariance():
    """Verify changing non-semantic metadata does NOT alter digest.

    Advisory freshness, timestamps, and reasons are excluded.
    """
    scope = _make_scope()
    plan = _make_plan()
    policy = RetrievalPolicy()

    fact = CanonicalFactView(
        record_id=uuid4(),
        logical_id="ent_main",
        kind="service",
        name="MainService",
        status="confirmed",
    )

    gen_id = uuid4()
    obs_initial = SourceObservation(
        source_kind=SourceKind.SEARCH,
        contract_version="1.0.0",
        generation_id=gen_id,
        index_uuid="idx_abc123",
        freshness=FreshnessState.CURRENT,
        is_current_version=True,
        freshness_reason="observed_at_now",
        observed_at=datetime.now(UTC),
    )

    builder = ContextBuilder(
        scope=scope,
        plan=plan.model_copy(
            update={"policy_fingerprint": policy.compute_fingerprint()}
        ),
        policy=policy,
    )
    bundle_initial = builder.build_bundle(
        source_observations=[obs_initial],
        facts=[fact],
    )

    # Change advisory freshness, timestamps, and reason
    obs_modified = SourceObservation(
        source_kind=SourceKind.SEARCH,
        contract_version="1.0.0",
        generation_id=gen_id,
        index_uuid="idx_abc123",
        freshness=FreshnessState.UNKNOWN,
        is_current_version=None,
        freshness_reason="not_observed_in_bounded_retrieval",
        observed_at=datetime(2020, 1, 1, tzinfo=UTC),
    )

    bundle_modified = builder.build_bundle(
        source_observations=[obs_modified],
        facts=[fact],
    )

    assert bundle_initial.semantic_digest == bundle_modified.semantic_digest


def test_semantic_digest_sensitivity():
    """Verify that changing semantic content alters the semantic digest."""
    scope = _make_scope()
    plan = _make_plan()
    policy = RetrievalPolicy()

    fact_base = CanonicalFactView(
        record_id=uuid4(),
        logical_id="ent_service",
        kind="service",
        name="UserService",
        status="confirmed",
    )
    fact_altered = CanonicalFactView(
        record_id=fact_base.record_id,
        logical_id="ent_service",
        kind="service",
        name="UserServiceAltered",
        status="confirmed",
    )

    builder = ContextBuilder(
        scope=scope,
        plan=plan.model_copy(
            update={"policy_fingerprint": policy.compute_fingerprint()}
        ),
        policy=policy,
    )
    bundle_base = builder.build_bundle(facts=[fact_base])
    bundle_altered = builder.build_bundle(facts=[fact_altered])

    assert bundle_base.semantic_digest != bundle_altered.semantic_digest


def test_deep_immutability_and_extra_fields_forbidden():
    """Verify ContextBundle and nested views forbid mutation and extra fields."""
    scope = _make_scope()
    plan = _make_plan()
    policy = RetrievalPolicy()

    builder = ContextBuilder(
        scope=scope,
        plan=plan.model_copy(
            update={"policy_fingerprint": policy.compute_fingerprint()}
        ),
        policy=policy,
    )
    bundle = builder.build_bundle()

    # Mutation raises error
    with pytest.raises(ValidationError):
        bundle.outcome = RetrievalOutcome.PARTIAL  # type: ignore

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        ContextBundle(
            c3_version=C3_CONTRACT_VERSION,
            scope=scope,
            plan=plan,
            policy_fingerprint="0" * 64,
            coverage=Coverage(),
            limits_and_usage=LimitsAndUsage(
                max_facts=10,
                max_relationships=10,
                max_evidence=10,
                max_output_bytes=10000,
            ),
            outcome=RetrievalOutcome.COMPLETE,
            semantic_digest="0" * 64,
            malicious_injected_field="attack",  # type: ignore
        )


def test_wire_byte_capacity_exceeded():
    """Verify RetrievalCapacityExceededError is raised on wire overflow.

    Ensures total output bytes stay within configured budget.
    """
    scope = _make_scope()
    plan = _make_plan()
    # Configure tiny 1024 bytes limit
    policy = RetrievalPolicy(max_output_bytes=1024)

    large_facts = [
        CanonicalFactView(
            record_id=uuid4(),
            logical_id=f"large_entity_{i:03d}",
            kind="service",
            name=f"LargeService{i}" * 10,
            status="confirmed",
            metadata={"description": "Very long description data " * 5},
        )
        for i in range(15)
    ]

    builder = ContextBuilder(
        scope=scope,
        plan=plan.model_copy(
            update={"policy_fingerprint": policy.compute_fingerprint()}
        ),
        policy=policy,
    )
    with pytest.raises(RetrievalCapacityExceededError, match="ContextBundle wire size"):
        builder.build_bundle(facts=large_facts)


def test_outcome_classification():
    """Verify outcome logic classifies COMPLETE, PARTIAL, AMBIGUOUS, and NO_EVIDENCE."""
    scope = _make_scope()
    plan = _make_plan()
    policy = RetrievalPolicy(max_selected_facts=1)

    builder = ContextBuilder(
        scope=scope,
        plan=plan.model_copy(
            update={"policy_fingerprint": policy.compute_fingerprint()}
        ),
        policy=policy,
    )

    # 1. NO_EVIDENCE: 0 facts, 0 evidence
    b_empty = builder.build_bundle()
    assert b_empty.outcome == RetrievalOutcome.NO_EVIDENCE

    # 2. COMPLETE: 1 fact within limit 1
    f1 = CanonicalFactView(
        record_id=uuid4(),
        logical_id="f1",
        kind="service",
        name="F1",
        status="confirmed",
    )
    b_complete = builder.build_bundle(facts=[f1])
    assert b_complete.outcome == RetrievalOutcome.COMPLETE

    # 3. PARTIAL: 2 facts exceeding max_selected_facts=1 -> truncated
    f2 = CanonicalFactView(
        record_id=uuid4(),
        logical_id="f2",
        kind="service",
        name="F2",
        status="confirmed",
    )
    b_partial = builder.build_bundle(facts=[f1, f2])
    assert b_partial.outcome == RetrievalOutcome.PARTIAL
    assert len(b_partial.facts) == 1
    assert any(o.reason == "entities_budget_exceeded" for o in b_partial.omissions)

    # 4. AMBIGUOUS: resolved subject has state AMBIGUOUS
    subj_ambig = ResolvedSubject(
        selector=SubjectSelector.from_entity_name("AmbigName"),
        state=ResolutionState.AMBIGUOUS,
    )
    b_ambig = builder.build_bundle(
        resolved_subjects=[subj_ambig],
        facts=[f1],
    )
    assert b_ambig.outcome == RetrievalOutcome.AMBIGUOUS
