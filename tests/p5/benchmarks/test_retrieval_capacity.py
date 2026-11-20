"""Bounded retrieval capacity and canonical resolution benchmarks.

Measures KnowledgeQueryService scaling, memory attribution, and canonical
resolution times across representative models per §7A.5 and §7A.11.
"""

from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from backend.platform.knowledge.context import ContextBuilder
from backend.platform.knowledge.evidence import EvidencePlanner
from backend.platform.knowledge.retrieval import (
    KnowledgeQueryService,
    resolve_subject,
)
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalFactView,
    CanonicalReadPort,
    ConflictView,
    EvidenceItemView,
    KnowledgeQueryRequest,
    RelationshipView,
    ResolutionState,
    RetrievalOperation,
    RetrievalOutcome,
    RetrievalPlan,
    RetrievalPrincipal,
    RetrievalScope,
    SourceKind,
    SubjectSelector,
    UnresolvedView,
)


def current_rss_mib() -> float | None:
    """Current per-process RSS (Linux procfs), safely None on other platforms."""
    try:
        with open("/proc/self/status") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return None


class InMemoryBenchmarkCanonicalPort(CanonicalReadPort):
    def __init__(self, scope: RetrievalScope) -> None:
        self.scope = scope
        self.entities: list[CanonicalFactView] = []
        self.relationships: list[RelationshipView] = []
        self.evidence: list[EvidenceItemView] = []
        self.conflicts: list[ConflictView] = []
        self.unresolved: list[UnresolvedView] = []
        self.call_counts = {
            "get_version": 0,
            "get_entity": 0,
            "list_entities": 0,
            "list_relationships": 0,
            "list_evidence": 0,
            "list_conflicts": 0,
            "list_unresolved": 0,
        }

    def get_version(self, version_id: UUID, project_id: UUID) -> RetrievalScope:
        self.call_counts["get_version"] += 1
        return self.scope

    def get_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> CanonicalFactView | None:
        self.call_counts["get_entity"] += 1
        for e in self.entities:
            if e.record_id == entity_id:
                return e
        return None

    def list_entities(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int, **kwargs
    ):
        self.call_counts["list_entities"] += 1
        paged = self.entities[offset : offset + limit]
        return tuple(paged), len(self.entities)

    def list_relationships(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int, **kwargs
    ):
        self.call_counts["list_relationships"] += 1
        paged = self.relationships[offset : offset + limit]
        return tuple(paged), len(self.relationships)

    def list_evidence(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int, **kwargs
    ):
        self.call_counts["list_evidence"] += 1
        paged = self.evidence[offset : offset + limit]
        return tuple(paged), len(self.evidence)

    def list_unresolved(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ):
        self.call_counts["list_unresolved"] += 1
        paged = self.unresolved[offset : offset + limit]
        return tuple(paged), len(self.unresolved)

    def list_conflicts(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ):
        self.call_counts["list_conflicts"] += 1
        paged = self.conflicts[offset : offset + limit]
        return tuple(paged), len(self.conflicts)


def test_representative_retrieval_resolution_benchmark():
    prj = uuid4()
    ver = uuid4()
    scope = RetrievalScope(
        project_id=prj,
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=ver,
        sequence_number=1,
        canonical_digest="f" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        published_at=datetime.now(UTC),
    )
    canonical = InMemoryBenchmarkCanonicalPort(scope)

    # Populate 300 entities
    num_entities = 300
    for i in range(num_entities):
        canonical.entities.append(
            CanonicalFactView(
                record_id=uuid4(),
                logical_id=f"architecture://entity/service/node_{i}",
                kind="service",
                name=f"ServiceNode{i}",
                namespace=("app", f"domain_{i // 25}"),
                status="CONFIRMED",
                evidence_count=2,
                evidence_references=(f"ev-{i}-1", f"ev-{i}-2"),
            )
        )

    # Populate 500 relationships
    num_relationships = 500
    for i in range(num_relationships):
        src_idx = i % num_entities
        tgt_idx = (i + 1) % num_entities
        canonical.relationships.append(
            RelationshipView(
                record_id=uuid4(),
                logical_id=f"architecture://relationship/calls/rel_{i}",
                kind="calls",
                status="CONFIRMED",
                source_logical_id=f"architecture://entity/service/node_{src_idx}",
                target_logical_id=f"architecture://entity/service/node_{tgt_idx}",
            )
        )

    principal = RetrievalPrincipal(actor_id=uuid4(), project_id=prj, role="member")
    policy = RetrievalPolicy(max_chain_work_units=10000)
    secret_key = "test-retrieval-cursor-secret-key-32b"
    svc = KnowledgeQueryService(canonical, policy=policy, cursor_secret_key=secret_key)

    # Measure resolution of early, middle, late, and missing entities by name
    early_target = canonical.entities[5]
    mid_target = canonical.entities[150]
    late_target = canonical.entities[295]

    before_rss = current_rss_mib()
    started = perf_counter()

    # Early lookup
    res_early = resolve_subject(
        SubjectSelector.from_entity_name(
            early_target.name, namespace=early_target.namespace
        ),
        canonical,
        ver,
        prj,
        max_scan_rows=policy.canonical_max_rows_per_collection,
    )
    assert res_early.state == ResolutionState.RESOLVED
    assert res_early.selected_id == early_target.record_id

    # Mid lookup
    res_mid = resolve_subject(
        SubjectSelector.from_entity_name(
            mid_target.name, namespace=mid_target.namespace
        ),
        canonical,
        ver,
        prj,
        max_scan_rows=policy.canonical_max_rows_per_collection,
    )
    assert res_mid.state == ResolutionState.RESOLVED

    # Late lookup
    res_late = resolve_subject(
        SubjectSelector.from_entity_name(
            late_target.name, namespace=late_target.namespace
        ),
        canonical,
        ver,
        prj,
        max_scan_rows=policy.canonical_max_rows_per_collection,
    )
    assert res_late.state == ResolutionState.RESOLVED

    # Full KnowledgeQueryService lookup
    query_req = KnowledgeQueryRequest(
        project_id=prj,
        architecture_version_id=ver,
        operation=RetrievalOperation.LOOKUP,
        subject=SubjectSelector.from_record_id("entity", mid_target.record_id),
    )
    query_resp = svc.query(query_req, principal=principal)
    assert query_resp.outcome == RetrievalOutcome.COMPLETE
    assert len(query_resp.facts) == 1

    # Full KnowledgeQueryService relationships
    rel_req = KnowledgeQueryRequest(
        project_id=prj,
        architecture_version_id=ver,
        operation=RetrievalOperation.RELATIONSHIPS,
        subject=SubjectSelector.from_record_id("entity", early_target.record_id),
    )
    rel_resp = svc.query(rel_req, principal=principal)
    assert len(rel_resp.relationships) > 0

    duration_s = perf_counter() - started
    after_rss = current_rss_mib()

    wire_size = len(query_resp.model_dump_json().encode("utf-8"))
    assert wire_size < policy.max_output_bytes
    assert duration_s < 2.0

    print(
        "P5_M3_MEASUREMENT "
        + json.dumps(
            {
                "test": "representative_retrieval_resolution",
                "python": platform.python_version(),
                "duration_seconds": round(duration_s, 6),
                "total_entities": num_entities,
                "total_relationships": num_relationships,
                "wire_size_bytes": wire_size,
                "calls": canonical.call_counts,
                "before_rss_mib": before_rss,
                "after_rss_mib": after_rss,
            }
        )
    )


def test_context_and_evidence_assembly_benchmark():
    """Benchmark ContextBuilder and EvidencePlanner under high-fanout models.

    Adheres to §7A.7 and §7A.8 specifications.
    """
    prj = uuid4()
    ver = uuid4()
    scope = RetrievalScope(
        project_id=prj,
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=ver,
        sequence_number=1,
        canonical_digest="e" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        published_at=datetime.now(UTC),
    )
    policy = RetrievalPolicy(max_chain_work_units=10000)
    canonical = InMemoryBenchmarkCanonicalPort(scope)

    # 50 facts, 100 relationships, 150 evidence items, 10 conflicts, 10 unresolved
    num_facts = 50
    num_relationships = 100
    num_evidence = 150

    facts: list[CanonicalFactView] = []
    for i in range(num_facts):
        ev_refs = tuple(
            f"ev_{i * 3 + j}" for j in range(3) if (i * 3 + j) < num_evidence
        )
        facts.append(
            CanonicalFactView(
                record_id=uuid4(),
                logical_id=f"fact_{i}",
                kind="service" if i % 2 == 0 else "database",
                name=f"Service_{i}",
                status="confirmed",
                evidence_references=ev_refs,
            )
        )
    canonical.entities = facts

    relationships: list[RelationshipView] = []
    for i in range(num_relationships):
        src_idx = i % num_facts
        tgt_idx = (i + 1) % num_facts
        relationships.append(
            RelationshipView(
                record_id=uuid4(),
                logical_id=f"rel_{i}",
                kind="calls",
                status="confirmed",
                source_logical_id=f"fact_{src_idx}",
                target_logical_id=f"fact_{tgt_idx}",
                evidence_references=(f"ev_{i % num_evidence}",),
            )
        )
    canonical.relationships = relationships

    evidence_items: list[EvidenceItemView] = []
    for i in range(num_evidence):
        evidence_items.append(
            EvidenceItemView(
                record_id=uuid4(),
                logical_id=f"ev_{i}",
                source_record_type="ast",
                path=f"src/module_{i % 10}/file_{i}.py",
                polarity="supporting" if i % 5 != 0 else "conflicting",
                strength="direct_source" if i % 2 == 0 else "framework_structural",
                subject_references=(f"fact_{i % num_facts}",),
            )
        )
    canonical.evidence = evidence_items

    conflicts: list[ConflictView] = []
    for i in range(10):
        conflicts.append(
            ConflictView(
                record_id=uuid4(),
                logical_id=f"conf_{i}",
                conflict_type="competing_declaration",
                subject_key=f"fact_{i}",
                details={"framework": "fastapi"},
            )
        )
    canonical.conflicts = conflicts

    unresolved: list[UnresolvedView] = []
    for i in range(10):
        unresolved.append(
            UnresolvedView(
                record_id=uuid4(),
                logical_id=f"unres_{i}",
                reason="not_found",
                unresolved_type="external_service",
                source_logical_id=f"fact_{i}",
                target_descriptor=f"External_{i}",
                details={"database_engine": "postgres"},
            )
        )
    canonical.unresolved = unresolved

    before_rss = current_rss_mib()
    started = perf_counter()

    # Step 1: Run EvidencePlanner
    planner = EvidencePlanner(canonical_port=canonical, policy=policy)
    plan_res = planner.plan_evidence(
        version_id=ver,
        project_id=prj,
        facts=facts[:25],
        relationships=relationships[:50],
        include_evidence=True,
        include_conflicts=True,
        include_unresolved=True,
    )
    assert len(plan_res.evidence) > 0
    assert len(plan_res.conflicts) > 0

    # Step 2: Run ContextBuilder
    plan = RetrievalPlan(
        strategy_version="1.0.0",
        request_fingerprint="f" * 64,
        operations=(
            RetrievalOperation.LOOKUP,
            RetrievalOperation.RELATIONSHIPS,
            RetrievalOperation.EVIDENCE,
        ),
        subjects=tuple(
            SubjectSelector.from_logical_id("entity", f.logical_id) for f in facts[:5]
        ),
        required_sources=(SourceKind.CANONICAL,),
        optional_sources=(),
        policy_fingerprint=policy.compute_fingerprint(),
        budget_snapshot={"limit": 25},
    )

    builder = ContextBuilder(scope=scope, plan=plan, policy=policy)
    bundle = builder.build_bundle(
        facts=facts[:25],
        relationships=relationships[:50],
        evidence=plan_res.evidence,
        unresolved=plan_res.unresolved,
        conflicts=plan_res.conflicts,
        omissions=plan_res.omissions,
    )
    assert bundle.outcome == RetrievalOutcome.COMPLETE
    assert len(bundle.semantic_digest) == 64

    duration_s = perf_counter() - started
    after_rss = current_rss_mib()

    wire_size = bundle.limits_and_usage.total_output_bytes
    assert wire_size > 0
    assert wire_size <= policy.max_output_bytes
    assert duration_s < 1.0

    print(
        "P5_M3_MEASUREMENT "
        + json.dumps(
            {
                "test": "context_and_evidence_assembly",
                "python": platform.python_version(),
                "duration_seconds": round(duration_s, 6),
                "total_facts": len(bundle.facts),
                "total_relationships": len(bundle.relationships),
                "total_evidence": len(bundle.evidence),
                "wire_size_bytes": wire_size,
                "before_rss_mib": before_rss,
                "after_rss_mib": after_rss,
            }
        )
    )
