"""P5-C3 Evidence Planner and canonical evidence resolution.

This module implements the EvidencePlanner responsible for bounded resolution,
deduplication, strength ordering, opposing evidence preservation, and safe
content filtering adhering to §7A.7 and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.platform.analysis.architecture.model import (
    ArchitectureEvidencePolarity,
    ArchitectureEvidenceStrength,
)
from backend.platform.knowledge.projection import filter_safe_metadata
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalFactView,
    CanonicalReadPort,
    ConflictView,
    EvidenceItemView,
    OmissionSummary,
    RelationshipView,
    RetrievalCapacityExceededError,
    SourceKind,
    UnresolvedView,
)

STRENGTH_RANK_MAP: Final[dict[str, int]] = {
    ArchitectureEvidenceStrength.DIRECT_SOURCE.value: 5,
    ArchitectureEvidenceStrength.FRAMEWORK_STRUCTURAL.value: 4,
    ArchitectureEvidenceStrength.CONFIGURATION.value: 3,
    ArchitectureEvidenceStrength.DEPENDENCY.value: 2,
    ArchitectureEvidenceStrength.DOCUMENTATION.value: 1,
}


def evidence_strength_rank(strength: str | None) -> int:
    """Return numeric rank for evidence strength (5 down to 1, 0 for unknown)."""
    if not strength:
        return 0
    return STRENGTH_RANK_MAP.get(strength.lower(), 0)


def evidence_sort_key(ev: EvidenceItemView) -> tuple[int, int, str]:
    """Deterministic sorting key: strength rank, polarity, logical_id.

    Rank is descending, polarity prioritizes conflicting evidence, and
    logical_id breaks ties ascending.
    """
    rank = evidence_strength_rank(ev.strength)
    polarity_prio = (
        1
        if ev.polarity.lower() == ArchitectureEvidencePolarity.CONFLICTING.value
        else 0
    )
    return (-rank, -polarity_prio, ev.logical_id)


class EvidencePlanningResult(BaseModel):
    """Result of evidence, conflict, and unresolved planning (§7A.7)."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    evidence: tuple[EvidenceItemView, ...] = ()
    unresolved: tuple[UnresolvedView, ...] = ()
    conflicts: tuple[ConflictView, ...] = ()
    omissions: tuple[OmissionSummary, ...] = ()
    scanned_count: int = Field(default=0, ge=0)
    considered_count: int = Field(default=0, ge=0)
    selected_count: int = Field(default=0, ge=0)
    conflict_coverage_incomplete: bool = False


class EvidencePlanner:
    """Plans, resolves, and deduplicates evidence, conflicts, and unresolved items

    from canonical architecture storage adhering to bounded retrieval policies.
    """

    def __init__(
        self, canonical_port: CanonicalReadPort, policy: RetrievalPolicy
    ) -> None:
        self._canonical_port = canonical_port
        self._policy = policy

    def plan_evidence(
        self,
        *,
        version_id: UUID,
        project_id: UUID,
        facts: Sequence[CanonicalFactView],
        relationships: Sequence[RelationshipView],
        max_evidence: int | None = None,
        include_evidence: bool = True,
        include_conflicts: bool = True,
        include_unresolved: bool = True,
    ) -> EvidencePlanningResult:
        """Plan and resolve evidence, conflicts, and unresolved records.

        Operates on canonical facts and relationships under bounded limits.
        """
        budget_limit = (
            max_evidence
            if max_evidence is not None
            else self._policy.max_selected_evidence
        )
        if budget_limit < 1:
            budget_limit = 1

        omissions: list[OmissionSummary] = []
        selected_evidence: list[EvidenceItemView] = []
        selected_conflicts: list[ConflictView] = []
        selected_unresolved: list[UnresolvedView] = []
        conflict_coverage_incomplete = False

        scanned_count = 0
        considered_count = 0

        # Collect references from facts and relationships
        fact_logical_ids = {f.logical_id for f in facts}
        rel_logical_ids = {r.logical_id for r in relationships}
        all_referenced_evidence_keys: set[str] = set()
        for f in facts:
            all_referenced_evidence_keys.update(f.evidence_references)
        for r in relationships:
            all_referenced_evidence_keys.update(r.evidence_references)

        # 1. Resolve Evidence if requested
        if include_evidence and (facts or relationships):
            # Fetch evidence in pages bounded by scan budget
            page_size = self._policy.canonical_page_size
            offset = 0
            scanned_evidence: list[EvidenceItemView] = []

            while offset < self._policy.canonical_max_rows_per_collection:
                batch_limit = min(
                    page_size,
                    self._policy.canonical_max_rows_per_collection - offset,
                )
                ev_items, total_ev = self._canonical_port.list_evidence(
                    version_id=version_id,
                    project_id=project_id,
                    limit=batch_limit,
                    offset=offset,
                )
                scanned_count += len(ev_items)
                scanned_evidence.extend(ev_items)
                offset += len(ev_items)
                if not ev_items or offset >= total_ev:
                    break

            # Filter evidence items relevant to selected facts/relationships
            seen_evidence_ids: set[str] = set()
            for ev in scanned_evidence:
                considered_count += 1
                is_referenced = (
                    ev.logical_id in all_referenced_evidence_keys
                    or any(ref in fact_logical_ids for ref in ev.subject_references)
                    or any(ref in rel_logical_ids for ref in ev.subject_references)
                )
                if is_referenced:
                    dedupe_key = ev.logical_id
                    if dedupe_key not in seen_evidence_ids:
                        seen_evidence_ids.add(dedupe_key)
                        selected_evidence.append(ev)

            # Deterministic sorting
            selected_evidence.sort(key=evidence_sort_key)

            # Enforce evidence budget
            if len(selected_evidence) > budget_limit:
                omitted_count = len(selected_evidence) - budget_limit
                omissions.append(
                    OmissionSummary(
                        source=SourceKind.CANONICAL,
                        reason="evidence_budget_exceeded",
                        omitted_count=omitted_count,
                        details={
                            "requested_limit": budget_limit,
                            "total_matched": len(selected_evidence),
                        },
                    )
                )
                selected_evidence = selected_evidence[:budget_limit]

        # 2. Resolve Conflicts if requested
        if include_conflicts and facts:
            page_size = self._policy.canonical_page_size
            offset = 0
            scanned_conflicts: list[ConflictView] = []

            while offset < self._policy.canonical_max_rows_per_collection:
                batch_limit = min(
                    page_size,
                    self._policy.canonical_max_rows_per_collection - offset,
                )
                conf_items, total_conf = self._canonical_port.list_conflicts(
                    version_id=version_id,
                    project_id=project_id,
                    limit=batch_limit,
                    offset=offset,
                )
                scanned_count += len(conf_items)
                scanned_conflicts.extend(conf_items)
                offset += len(conf_items)
                if (
                    offset < total_conf
                    and offset >= self._policy.canonical_max_rows_per_collection
                ):
                    conflict_coverage_incomplete = True
                if not conf_items or offset >= total_conf:
                    break

            seen_conflicts: set[str] = set()
            for conf in scanned_conflicts:
                considered_count += 1
                is_related = False
                if conf.subject_key and (
                    conf.subject_key in fact_logical_ids
                    or conf.subject_key in rel_logical_ids
                ):
                    is_related = True
                elif any(
                    ref in all_referenced_evidence_keys
                    for ref in conf.evidence_references
                ):
                    is_related = True

                if is_related and conf.logical_id not in seen_conflicts:
                    seen_conflicts.add(conf.logical_id)
                    # Sanitize details
                    safe_details, omitted_fields = filter_safe_metadata(conf.details)
                    if omitted_fields:
                        omissions.append(
                            OmissionSummary(
                                source=SourceKind.CANONICAL,
                                reason="conflict_safe_field_exclusion",
                                omitted_count=sum(omitted_fields.values()),
                                details={
                                    "conflict_id": conf.logical_id,
                                    "omitted_keys": list(omitted_fields.keys()),
                                },
                            )
                        )
                    sanitized_conf = ConflictView(
                        record_id=conf.record_id,
                        logical_id=conf.logical_id,
                        conflict_type=conf.conflict_type,
                        subject_key=conf.subject_key,
                        details=safe_details,
                        evidence_references=conf.evidence_references,
                    )
                    selected_conflicts.append(sanitized_conf)

            # Sort conflicts deterministically by logical_id
            selected_conflicts.sort(key=lambda c: c.logical_id)

            # If required subject conflicts exist and cannot be disclosed due to budget
            if self._policy.max_selected_conflicts < len(selected_conflicts):
                raise RetrievalCapacityExceededError(
                    "Cannot fit required subject conflict disclosure "
                    "within configured conflict budget"
                )

        # 3. Resolve Unresolved items if requested
        if include_unresolved and facts:
            page_size = self._policy.canonical_page_size
            offset = 0
            scanned_unresolved: list[UnresolvedView] = []

            while offset < self._policy.canonical_max_rows_per_collection:
                batch_limit = min(
                    page_size,
                    self._policy.canonical_max_rows_per_collection - offset,
                )
                unres_items, total_unres = self._canonical_port.list_unresolved(
                    version_id=version_id,
                    project_id=project_id,
                    limit=batch_limit,
                    offset=offset,
                )
                scanned_count += len(unres_items)
                scanned_unresolved.extend(unres_items)
                offset += len(unres_items)
                if not unres_items or offset >= total_unres:
                    break

            seen_unresolved: set[str] = set()
            for unres in scanned_unresolved:
                considered_count += 1
                if (
                    unres.source_logical_id
                    and unres.source_logical_id in fact_logical_ids
                ):
                    if unres.logical_id not in seen_unresolved:
                        seen_unresolved.add(unres.logical_id)
                        safe_details, omitted_fields = filter_safe_metadata(
                            unres.details
                        )
                        if omitted_fields:
                            omissions.append(
                                OmissionSummary(
                                    source=SourceKind.CANONICAL,
                                    reason="unresolved_safe_field_exclusion",
                                    omitted_count=sum(omitted_fields.values()),
                                    details={
                                        "unresolved_id": unres.logical_id,
                                        "omitted_keys": list(omitted_fields.keys()),
                                    },
                                )
                            )
                        sanitized_unres = UnresolvedView(
                            record_id=unres.record_id,
                            logical_id=unres.logical_id,
                            reason=unres.reason,
                            unresolved_type=unres.unresolved_type,
                            source_logical_id=unres.source_logical_id,
                            target_descriptor=unres.target_descriptor,
                            details=safe_details,
                        )
                        selected_unresolved.append(sanitized_unres)

            # Sort unresolved deterministically
            selected_unresolved.sort(key=lambda u: u.logical_id)

        selected_count = (
            len(selected_evidence) + len(selected_conflicts) + len(selected_unresolved)
        )

        return EvidencePlanningResult(
            evidence=tuple(selected_evidence),
            unresolved=tuple(selected_unresolved),
            conflicts=tuple(selected_conflicts),
            omissions=tuple(omissions),
            scanned_count=scanned_count,
            considered_count=considered_count,
            selected_count=selected_count,
            conflict_coverage_incomplete=conflict_coverage_incomplete,
        )


__all__ = [
    "EvidencePlanner",
    "EvidencePlanningResult",
    "evidence_sort_key",
    "evidence_strength_rank",
]
