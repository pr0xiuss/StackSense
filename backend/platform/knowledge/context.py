"""P5-C3 ContextBuilder, bounded context assembly, and deterministic semantic digest.

This module implements the pure ContextBuilder responsible for deduplication,
selection packing, deep immutability, omission tracking, and deterministic
C3 semantic digest calculation adhering to §7A.8 and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any, Final

from backend.platform.knowledge.evidence import evidence_sort_key
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    C3_CONTRACT_VERSION,
    CanonicalFactView,
    ConflictView,
    ContextBundle,
    Coverage,
    EvidenceItemView,
    LimitsAndUsage,
    OmissionSummary,
    RelationshipView,
    ResolutionState,
    ResolvedSubject,
    RetrievalCapacityExceededError,
    RetrievalOutcome,
    RetrievalPlan,
    RetrievalScope,
    SelectionRationale,
    SourceKind,
    SourceObservation,
    UnresolvedView,
)

C3_DIGEST_CONTRACT: Final[str] = "C3"
C3_DIGEST_KIND: Final[str] = "context"


def _serialize_scope_for_digest(scope: RetrievalScope) -> dict[str, Any]:
    """Allowlisted projection of canonical scope for semantic digest."""
    return {
        "project_id": str(scope.project_id),
        "repository_id": str(scope.repository_id),
        "analysis_id": str(scope.analysis_id),
        "snapshot_id": str(scope.snapshot_id),
        "architecture_version_id": str(scope.architecture_version_id),
        "sequence_number": scope.sequence_number,
        "canonical_digest": scope.canonical_digest,
    }


def _serialize_used_sources_for_digest(
    observations: Sequence[SourceObservation],
) -> list[dict[str, Any]]:
    """Allowlisted projection of participating sources (no advisory/timing data)."""
    used: list[dict[str, Any]] = []
    for obs in sorted(observations, key=lambda o: o.source_kind.value):
        used.append(
            {
                "source_kind": obs.source_kind.value,
                "contract_version": obs.contract_version,
                "generation_id": str(obs.generation_id) if obs.generation_id else None,
                "index_uuid": obs.index_uuid,
            }
        )
    return used


def _serialize_fact_for_digest(f: CanonicalFactView) -> dict[str, Any]:
    return {
        "record_id": str(f.record_id),
        "logical_id": f.logical_id,
        "kind": f.kind,
        "name": f.name,
        "namespace": list(f.namespace) if f.namespace else None,
        "status": f.status,
        "metadata": f.metadata,
        "evidence_references": sorted(f.evidence_references),
    }


def _serialize_relationship_for_digest(r: RelationshipView) -> dict[str, Any]:
    return {
        "record_id": str(r.record_id),
        "logical_id": r.logical_id,
        "kind": r.kind,
        "status": r.status,
        "source_logical_id": r.source_logical_id,
        "target_logical_id": r.target_logical_id,
        "evidence_references": sorted(r.evidence_references),
    }


def _serialize_evidence_for_digest(ev: EvidenceItemView) -> dict[str, Any]:
    return {
        "record_id": str(ev.record_id),
        "logical_id": ev.logical_id,
        "source_record_type": ev.source_record_type,
        "path": ev.path,
        "range_data": ev.range_data,
        "polarity": ev.polarity,
        "strength": ev.strength,
        "producer_id": ev.producer_id,
        "producer_version": ev.producer_version,
        "source_fact_key": ev.source_fact_key,
        "subject_references": sorted(ev.subject_references),
    }


def _serialize_unresolved_for_digest(u: UnresolvedView) -> dict[str, Any]:
    return {
        "record_id": str(u.record_id),
        "logical_id": u.logical_id,
        "reason": u.reason,
        "unresolved_type": u.unresolved_type,
        "source_logical_id": u.source_logical_id,
        "target_descriptor": u.target_descriptor,
        "details": u.details,
    }


def _serialize_conflict_for_digest(c: ConflictView) -> dict[str, Any]:
    return {
        "record_id": str(c.record_id),
        "logical_id": c.logical_id,
        "conflict_type": c.conflict_type,
        "subject_key": c.subject_key,
        "details": c.details,
        "evidence_references": sorted(c.evidence_references),
    }


def _serialize_rationale_for_digest(r: SelectionRationale) -> dict[str, Any]:
    return {
        "code": r.code.value,
        "target_logical_id": r.target_logical_id,
        "target_kind": r.target_kind,
        "originating_operation": (
            r.originating_operation.value if r.originating_operation else None
        ),
        "hit_key": r.hit_key,
        "hop_distance": r.hop_distance,
    }


def compute_c3_semantic_digest(
    *,
    scope: RetrievalScope,
    plan: RetrievalPlan,
    policy_fingerprint: str,
    source_observations: Sequence[SourceObservation],
    resolved_subjects: Sequence[ResolvedSubject],
    facts: Sequence[CanonicalFactView],
    relationships: Sequence[RelationshipView],
    evidence: Sequence[EvidenceItemView],
    unresolved: Sequence[UnresolvedView],
    conflicts: Sequence[ConflictView],
    rationales: Sequence[SelectionRationale],
    coverage: Coverage,
    omissions: Sequence[OmissionSummary],
    limits_and_usage: LimitsAndUsage,
    outcome: RetrievalOutcome,
) -> str:
    """Compute the deterministic SHA-256 semantic digest for a ContextBundle.

    Adheres strictly to §7A.8:
    - Domain-tagged envelope with C3 contract metadata.
    - Explicit allowlisted projection of semantic elements only.
    - Complete exclusion of correlation IDs, timestamps, scan durations,
      floating search scores, and advisory freshness observations.
    - Compact sorted-key UTF-8 JSON encoding.
    """
    semantic_payload: dict[str, Any] = {
        "canonical_scope": _serialize_scope_for_digest(scope),
        "strategy_version": plan.strategy_version,
        "request_fingerprint": plan.request_fingerprint,
        "policy_fingerprint": policy_fingerprint,
        "used_sources": _serialize_used_sources_for_digest(source_observations),
        "resolved_subjects": [
            {
                "selector_type": s.selector.selector_type,
                "state": s.state.value,
                "selected_id": str(s.selected_id) if s.selected_id else None,
                "selected_logical_id": s.selected_logical_id,
                "selected_kind": s.selected_kind,
            }
            for s in resolved_subjects
        ],
        "facts": [_serialize_fact_for_digest(f) for f in facts],
        "relationships": [_serialize_relationship_for_digest(r) for r in relationships],
        "evidence": [_serialize_evidence_for_digest(e) for e in evidence],
        "unresolved": [_serialize_unresolved_for_digest(u) for u in unresolved],
        "conflicts": [_serialize_conflict_for_digest(c) for c in conflicts],
        "rationales": [_serialize_rationale_for_digest(r) for r in rationales],
        "coverage": {
            "considered_count": coverage.considered_count,
            "selected_count": coverage.selected_count,
            "scanned_count": coverage.scanned_count,
            "count_known": coverage.count_known,
            "exhausted": coverage.exhausted,
            "truncated": coverage.truncated,
            "omission_reasons": list(coverage.omission_reasons),
        },
        "omissions": [
            {
                "source": o.source.value,
                "reason": o.reason,
                "omitted_count": o.omitted_count,
            }
            for o in omissions
        ],
        "limits": {
            "max_facts": limits_and_usage.max_facts,
            "max_relationships": limits_and_usage.max_relationships,
            "max_evidence": limits_and_usage.max_evidence,
            "max_output_bytes": limits_and_usage.max_output_bytes,
        },
        "outcome": outcome.value,
    }

    envelope: dict[str, Any] = {
        "contract": C3_DIGEST_CONTRACT,
        "version": C3_CONTRACT_VERSION,
        "kind": C3_DIGEST_KIND,
        "semantic_payload": semantic_payload,
    }

    canonical_json = json.dumps(
        envelope,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(canonical_json).hexdigest()


class ContextBuilder:
    """Pure builder for bounded ContextBundle assembly.

    Performs deduplication, stable sorting, budget enforcement, deep validation,
    omission tracking, and deterministic semantic digest calculation.
    """

    def __init__(
        self,
        *,
        scope: RetrievalScope,
        plan: RetrievalPlan,
        policy: RetrievalPolicy,
    ) -> None:
        self._scope = scope
        self._plan = plan
        self._policy = policy

    def build_bundle(
        self,
        *,
        source_observations: Sequence[SourceObservation] = (),
        resolved_subjects: Sequence[ResolvedSubject] = (),
        facts: Sequence[CanonicalFactView] = (),
        relationships: Sequence[RelationshipView] = (),
        evidence: Sequence[EvidenceItemView] = (),
        unresolved: Sequence[UnresolvedView] = (),
        conflicts: Sequence[ConflictView] = (),
        rationales: Sequence[SelectionRationale] = (),
        coverage: Coverage | None = None,
        omissions: Sequence[OmissionSummary] = (),
    ) -> ContextBundle:
        """Assemble an immutable, validated ContextBundle."""
        policy_fingerprint = self._policy.compute_fingerprint()
        omission_list = list(omissions)

        # 1. Deduplicate and sort Facts
        seen_facts: dict[str, CanonicalFactView] = {}
        for f in facts:
            if f.logical_id not in seen_facts:
                seen_facts[f.logical_id] = f
        sorted_facts = sorted(seen_facts.values(), key=lambda f: (f.kind, f.logical_id))

        # 2. Deduplicate and sort Relationships
        seen_rels: dict[str, RelationshipView] = {}
        for r in relationships:
            if r.logical_id not in seen_rels:
                seen_rels[r.logical_id] = r
        sorted_rels = sorted(
            seen_rels.values(),
            key=lambda r: (
                r.kind,
                r.source_logical_id,
                r.target_logical_id,
                r.logical_id,
            ),
        )

        # 3. Deduplicate and sort Evidence
        seen_ev: dict[str, EvidenceItemView] = {}
        for ev in evidence:
            if ev.logical_id not in seen_ev:
                seen_ev[ev.logical_id] = ev
        sorted_ev = sorted(seen_ev.values(), key=evidence_sort_key)

        # 4. Deduplicate and sort Unresolved
        seen_unres: dict[str, UnresolvedView] = {}
        for u in unresolved:
            if u.logical_id not in seen_unres:
                seen_unres[u.logical_id] = u
        sorted_unres = sorted(
            seen_unres.values(), key=lambda u: (u.unresolved_type, u.logical_id)
        )

        # 5. Deduplicate and sort Conflicts
        seen_conf: dict[str, ConflictView] = {}
        for c in conflicts:
            if c.logical_id not in seen_conf:
                seen_conf[c.logical_id] = c
        sorted_conf = sorted(
            seen_conf.values(), key=lambda c: (c.conflict_type, c.logical_id)
        )

        # 6. Deduplicate and sort Rationales
        seen_rat: dict[tuple[str, str], SelectionRationale] = {}
        for rat in rationales:
            key = (rat.target_logical_id, rat.code.value)
            if key not in seen_rat:
                seen_rat[key] = rat
        sorted_rat = sorted(
            seen_rat.values(),
            key=lambda r: (r.target_kind, r.target_logical_id, r.code.value),
        )

        # 7. Deduplicate and sort Source Observations
        sorted_obs = sorted(source_observations, key=lambda o: o.source_kind.value)

        # 8. Sort Resolved Subjects
        sorted_subj = sorted(
            resolved_subjects,
            key=lambda s: s.selected_logical_id or s.selector.logical_id or "",
        )

        # Check bounds against policy budgets
        is_truncated = False
        if len(sorted_facts) > self._policy.max_selected_facts:
            omitted = len(sorted_facts) - self._policy.max_selected_facts
            omission_list.append(
                OmissionSummary(
                    source=SourceKind.CANONICAL,
                    reason="entities_budget_exceeded",
                    omitted_count=omitted,
                    details={"limit": self._policy.max_selected_facts},
                )
            )
            sorted_facts = sorted_facts[: self._policy.max_selected_facts]
            is_truncated = True

        if len(sorted_rels) > self._policy.max_selected_relationships:
            omitted = len(sorted_rels) - self._policy.max_selected_relationships
            omission_list.append(
                OmissionSummary(
                    source=SourceKind.CANONICAL,
                    reason="relationships_budget_exceeded",
                    omitted_count=omitted,
                    details={"limit": self._policy.max_selected_relationships},
                )
            )
            sorted_rels = sorted_rels[: self._policy.max_selected_relationships]
            is_truncated = True

        if len(sorted_ev) > self._policy.max_selected_evidence:
            omitted = len(sorted_ev) - self._policy.max_selected_evidence
            omission_list.append(
                OmissionSummary(
                    source=SourceKind.CANONICAL,
                    reason="evidence_budget_exceeded",
                    omitted_count=omitted,
                    details={"limit": self._policy.max_selected_evidence},
                )
            )
            sorted_ev = sorted_ev[: self._policy.max_selected_evidence]
            is_truncated = True

        # Determine Outcome (§7A.8)
        outcome = RetrievalOutcome.COMPLETE
        if any(s.state == ResolutionState.AMBIGUOUS for s in sorted_subj):
            outcome = RetrievalOutcome.AMBIGUOUS
        elif not sorted_facts and not sorted_ev:
            outcome = RetrievalOutcome.NO_EVIDENCE
        elif (
            is_truncated
            or any(o.reason.endswith("budget_exceeded") for o in omission_list)
            or any(s.state == ResolutionState.INCOMPLETE for s in sorted_subj)
            or any(s.state == ResolutionState.NOT_FOUND for s in sorted_subj)
        ):
            outcome = RetrievalOutcome.PARTIAL

        # Coverage assembly
        if coverage is not None:
            final_coverage = Coverage(
                considered_count=coverage.considered_count,
                selected_count=len(sorted_facts) + len(sorted_rels) + len(sorted_ev),
                scanned_count=coverage.scanned_count,
                count_known=coverage.count_known,
                exhausted=coverage.exhausted and not is_truncated,
                truncated=coverage.truncated or is_truncated,
                omission_reasons=tuple(sorted({o.reason for o in omission_list})),
            )
        else:
            total_items = len(sorted_facts) + len(sorted_rels) + len(sorted_ev)
            final_coverage = Coverage(
                considered_count=total_items,
                selected_count=total_items,
                scanned_count=total_items,
                count_known=True,
                exhausted=not is_truncated,
                truncated=is_truncated,
                omission_reasons=tuple(sorted({o.reason for o in omission_list})),
            )

        # Limits & usage accounting
        limits_and_usage = LimitsAndUsage(
            max_facts=self._policy.max_selected_facts,
            max_relationships=self._policy.max_selected_relationships,
            max_evidence=self._policy.max_selected_evidence,
            max_output_bytes=self._policy.max_output_bytes,
            facts_count=len(sorted_facts),
            relationships_count=len(sorted_rels),
            evidence_count=len(sorted_ev),
            unresolved_count=len(sorted_unres),
            conflicts_count=len(sorted_conf),
            total_output_bytes=0,
        )

        # Sort omissions
        sorted_omissions = sorted(
            omission_list, key=lambda o: (o.source.value, o.reason)
        )

        # Compute deterministic semantic digest
        semantic_digest = compute_c3_semantic_digest(
            scope=self._scope,
            plan=self._plan,
            policy_fingerprint=policy_fingerprint,
            source_observations=sorted_obs,
            resolved_subjects=sorted_subj,
            facts=sorted_facts,
            relationships=sorted_rels,
            evidence=sorted_ev,
            unresolved=sorted_unres,
            conflicts=sorted_conf,
            rationales=sorted_rat,
            coverage=final_coverage,
            omissions=sorted_omissions,
            limits_and_usage=limits_and_usage,
            outcome=outcome,
        )

        # Candidate bundle
        candidate_bundle = ContextBundle(
            c3_version=C3_CONTRACT_VERSION,
            scope=self._scope,
            plan=self._plan,
            policy_fingerprint=policy_fingerprint,
            source_observations=tuple(sorted_obs),
            resolved_subjects=tuple(sorted_subj),
            facts=tuple(sorted_facts),
            relationships=tuple(sorted_rels),
            evidence=tuple(sorted_ev),
            unresolved=tuple(sorted_unres),
            conflicts=tuple(sorted_conf),
            rationales=tuple(sorted_rat),
            coverage=final_coverage,
            omissions=tuple(sorted_omissions),
            limits_and_usage=limits_and_usage,
            outcome=outcome,
            semantic_digest=semantic_digest,
        )

        # Wire byte validation
        wire_json = candidate_bundle.model_dump_json()
        wire_bytes = len(wire_json.encode("utf-8"))

        if wire_bytes > self._policy.max_output_bytes:
            raise RetrievalCapacityExceededError(
                f"ContextBundle wire size ({wire_bytes} bytes) exceeds "
                f"configured limit ({self._policy.max_output_bytes} bytes)"
            )

        # Update limits_and_usage with measured total_output_bytes
        final_limits = LimitsAndUsage(
            max_facts=limits_and_usage.max_facts,
            max_relationships=limits_and_usage.max_relationships,
            max_evidence=limits_and_usage.max_evidence,
            max_output_bytes=limits_and_usage.max_output_bytes,
            facts_count=limits_and_usage.facts_count,
            relationships_count=limits_and_usage.relationships_count,
            evidence_count=limits_and_usage.evidence_count,
            unresolved_count=limits_and_usage.unresolved_count,
            conflicts_count=limits_and_usage.conflicts_count,
            total_output_bytes=wire_bytes,
        )

        return ContextBundle(
            c3_version=candidate_bundle.c3_version,
            scope=candidate_bundle.scope,
            plan=candidate_bundle.plan,
            policy_fingerprint=candidate_bundle.policy_fingerprint,
            source_observations=candidate_bundle.source_observations,
            resolved_subjects=candidate_bundle.resolved_subjects,
            facts=candidate_bundle.facts,
            relationships=candidate_bundle.relationships,
            evidence=candidate_bundle.evidence,
            unresolved=candidate_bundle.unresolved,
            conflicts=candidate_bundle.conflicts,
            rationales=candidate_bundle.rationales,
            coverage=candidate_bundle.coverage,
            omissions=candidate_bundle.omissions,
            limits_and_usage=final_limits,
            outcome=candidate_bundle.outcome,
            semantic_digest=candidate_bundle.semantic_digest,
        )


__all__ = [
    "C3_DIGEST_CONTRACT",
    "C3_DIGEST_KIND",
    "ContextBuilder",
    "compute_c3_semantic_digest",
]
