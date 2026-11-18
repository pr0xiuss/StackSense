"""Unit tests for P5-C3 EvidencePlanner and canonical evidence resolution.

Adheres to §7A.7 and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from backend.platform.knowledge.evidence import (
    EvidencePlanner,
    evidence_sort_key,
    evidence_strength_rank,
)
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalFactView,
    CanonicalReadPort,
    ConflictView,
    EvidenceItemView,
    RelationshipView,
    RetrievalCapacityExceededError,
    RetrievalNotFoundError,
    RetrievalScope,
    UnresolvedView,
)


class MockCanonicalPort(CanonicalReadPort):
    def __init__(self, scope: RetrievalScope) -> None:
        self.scope = scope
        self.entities: list[CanonicalFactView] = []
        self.relationships: list[RelationshipView] = []
        self.evidence: list[EvidenceItemView] = []
        self.conflicts: list[ConflictView] = []
        self.unresolved: list[UnresolvedView] = []

    def get_version(self, version_id: UUID, project_id: UUID) -> RetrievalScope:
        if (
            version_id != self.scope.architecture_version_id
            or project_id != self.scope.project_id
        ):
            raise RetrievalNotFoundError("Version not found")
        return self.scope

    def get_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> CanonicalFactView | None:
        for e in self.entities:
            if e.record_id == entity_id:
                return e
        return None

    def list_entities(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        **kwargs,
    ):
        paged = self.entities[offset : offset + limit]
        return tuple(paged), len(self.entities)

    def list_relationships(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        **kwargs,
    ):
        paged = self.relationships[offset : offset + limit]
        return tuple(paged), len(self.relationships)

    def list_evidence(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        **kwargs,
    ):
        paged = self.evidence[offset : offset + limit]
        return tuple(paged), len(self.evidence)

    def list_unresolved(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ):
        paged = self.unresolved[offset : offset + limit]
        return tuple(paged), len(self.unresolved)

    def list_conflicts(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ):
        paged = self.conflicts[offset : offset + limit]
        return tuple(paged), len(self.conflicts)


def _make_scope() -> RetrievalScope:
    return RetrievalScope(
        project_id=uuid4(),
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=uuid4(),
        sequence_number=1,
        canonical_digest="0" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        published_at=datetime.now(UTC),
    )


def test_evidence_strength_and_polarity_sorting():
    """Verify deterministic ranking and sorting key logic for evidence items."""
    assert evidence_strength_rank("direct_source") == 5
    assert evidence_strength_rank("framework_structural") == 4
    assert evidence_strength_rank("configuration") == 3
    assert evidence_strength_rank("dependency") == 2
    assert evidence_strength_rank("documentation") == 1
    assert evidence_strength_rank("unknown_strength") == 0
    assert evidence_strength_rank(None) == 0

    ev_direct_supp = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_direct_supp",
        source_record_type="ast",
        path="src/app.py",
        polarity="supporting",
        strength="direct_source",
    )
    ev_direct_conf = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_direct_conf",
        source_record_type="ast",
        path="src/app2.py",
        polarity="conflicting",
        strength="direct_source",
    )
    ev_doc = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_doc",
        source_record_type="doc",
        path="docs/arch.md",
        polarity="supporting",
        strength="documentation",
    )

    items = [ev_doc, ev_direct_supp, ev_direct_conf]
    items.sort(key=evidence_sort_key)

    # direct_source conflicting first, then direct_source supporting, then documentation
    assert items == [ev_direct_conf, ev_direct_supp, ev_doc]


def test_evidence_planner_resolves_and_deduplicates():
    """Verify EvidencePlanner resolves references and dedupes items.

    Operates on references from facts and relationships.
    """
    scope = _make_scope()
    port = MockCanonicalPort(scope)
    policy = RetrievalPolicy()

    ev1 = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_1",
        source_record_type="ast",
        path="src/models.py",
        polarity="supporting",
        strength="direct_source",
    )
    ev2 = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_2",
        source_record_type="ast",
        path="src/views.py",
        polarity="supporting",
        strength="framework_structural",
    )
    port.evidence = [ev1, ev2]

    fact = CanonicalFactView(
        record_id=uuid4(),
        logical_id="entity_service",
        kind="service",
        name="UserService",
        status="confirmed",
        evidence_references=("ev_1", "ev_2"),
    )
    rel = RelationshipView(
        record_id=uuid4(),
        logical_id="rel_calls",
        kind="calls",
        status="confirmed",
        source_logical_id="entity_service",
        target_logical_id="entity_db",
        evidence_references=("ev_1",),  # duplicate reference to ev_1
    )

    planner = EvidencePlanner(canonical_port=port, policy=policy)
    res = planner.plan_evidence(
        version_id=scope.architecture_version_id,
        project_id=scope.project_id,
        facts=[fact],
        relationships=[rel],
    )

    assert len(res.evidence) == 2
    ev_ids = [e.logical_id for e in res.evidence]
    assert ev_ids == ["ev_1", "ev_2"]  # deduped
    assert res.selected_count == 2
    assert res.scanned_count == 2


def test_evidence_preserves_actual_persisted_coordinates():
    """Verify source coordinates are preserved in their exact persisted shape.

    Retains lines, columns, byte offsets, and original markers.
    """
    scope = _make_scope()
    port = MockCanonicalPort(scope)
    policy = RetrievalPolicy()

    range_payload = {
        "start_line": 42,
        "end_line": 84,
        "start_col": 0,
        "end_col": 12,
        "start_byte": 1024,
        "end_byte": 2048,
    }
    ev = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_coord",
        source_record_type="ast",
        path="src/parser.py",
        range_data=range_payload,
        polarity="supporting",
        strength="direct_source",
        producer_id="custom_analyzer",
        producer_version="2.1.0",
        source_fact_key="symbol_entry",
    )
    port.evidence = [ev]

    fact = CanonicalFactView(
        record_id=uuid4(),
        logical_id="entity_parser",
        kind="component",
        name="Parser",
        status="confirmed",
        evidence_references=("ev_coord",),
    )

    planner = EvidencePlanner(canonical_port=port, policy=policy)
    res = planner.plan_evidence(
        version_id=scope.architecture_version_id,
        project_id=scope.project_id,
        facts=[fact],
        relationships=[],
    )

    assert len(res.evidence) == 1
    selected = res.evidence[0]
    assert selected.range_data == range_payload
    assert selected.producer_id == "custom_analyzer"
    assert selected.producer_version == "2.1.0"
    assert selected.source_fact_key == "symbol_entry"


def test_evidence_planner_sanitizes_conflict_and_unresolved_details():
    """Verify conflict and unresolved details are sanitized.

    Uses filter_safe_metadata and records safe exclusions.
    """
    scope = _make_scope()
    port = MockCanonicalPort(scope)
    policy = RetrievalPolicy()

    fact = CanonicalFactView(
        record_id=uuid4(),
        logical_id="ent_db",
        kind="database",
        name="PostgresDB",
        status="confirmed",
    )

    # Conflict with sensitive keys and unknown keys
    conf = ConflictView(
        record_id=uuid4(),
        logical_id="conf_1",
        conflict_type="schema_mismatch",
        subject_key="ent_db",
        details={
            "database_engine": "postgresql",
            "api_key": "secret_12345",  # sensitive
            "db_password": "supersecretpassword",  # sensitive
            "unrecognized_field": 42,  # outside allowed keys
        },
    )
    port.conflicts = [conf]

    # Unresolved with sensitive details
    unres = UnresolvedView(
        record_id=uuid4(),
        logical_id="unres_1",
        reason="not_found",
        unresolved_type="external_service",
        source_logical_id="ent_db",
        target_descriptor="AuthService",
        details={
            "token": "bearer_secret",
            "framework": "grpc",
        },
    )
    port.unresolved = [unres]

    planner = EvidencePlanner(canonical_port=port, policy=policy)
    res = planner.plan_evidence(
        version_id=scope.architecture_version_id,
        project_id=scope.project_id,
        facts=[fact],
        relationships=[],
        include_evidence=False,
        include_conflicts=True,
        include_unresolved=True,
    )

    assert len(res.conflicts) == 1
    sanitized_conf = res.conflicts[0]
    assert "api_key" not in sanitized_conf.details
    assert "db_password" not in sanitized_conf.details
    assert "unrecognized_field" not in sanitized_conf.details
    assert sanitized_conf.details.get("database_engine") == "postgresql"

    assert len(res.unresolved) == 1
    sanitized_unres = res.unresolved[0]
    assert "token" not in sanitized_unres.details
    assert sanitized_unres.details.get("framework") == "grpc"

    # Verify omission summaries were generated
    reasons = [o.reason for o in res.omissions]
    assert "conflict_safe_field_exclusion" in reasons
    assert "unresolved_safe_field_exclusion" in reasons


def test_evidence_planner_forbids_filesystem_access():
    """Verify EvidencePlanner never attempts to read actual source files from disk."""
    scope = _make_scope()
    port = MockCanonicalPort(scope)
    policy = RetrievalPolicy()

    ev = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev_secret_file",
        source_record_type="env",
        path=".env",
        polarity="supporting",
        strength="configuration",
    )
    port.evidence = [ev]

    fact = CanonicalFactView(
        record_id=uuid4(),
        logical_id="ent_config",
        kind="config",
        name="Config",
        status="confirmed",
        evidence_references=("ev_secret_file",),
    )

    def forbidden_open(*args, **kwargs):
        raise AssertionError(f"Forbidden filesystem open called with: {args}")

    with patch("builtins.open", side_effect=forbidden_open):
        planner = EvidencePlanner(canonical_port=port, policy=policy)
        res = planner.plan_evidence(
            version_id=scope.architecture_version_id,
            project_id=scope.project_id,
            facts=[fact],
            relationships=[],
        )

    assert len(res.evidence) == 1
    assert res.evidence[0].path == ".env"


def test_evidence_planner_conflict_capacity_exceeded():
    """Verify RetrievalCapacityExceededError is raised on conflict overflow.

    Ensures conflicts cannot be falsely omitted without disclosure.
    """
    scope = _make_scope()
    port = MockCanonicalPort(scope)
    policy = RetrievalPolicy(max_selected_conflicts=1)

    fact = CanonicalFactView(
        record_id=uuid4(),
        logical_id="ent_service",
        kind="service",
        name="Service",
        status="confirmed",
    )
    c1 = ConflictView(
        record_id=uuid4(),
        logical_id="conf_1",
        conflict_type="conflict_a",
        subject_key="ent_service",
    )
    c2 = ConflictView(
        record_id=uuid4(),
        logical_id="conf_2",
        conflict_type="conflict_b",
        subject_key="ent_service",
    )
    port.conflicts = [c1, c2]

    planner = EvidencePlanner(canonical_port=port, policy=policy)
    with pytest.raises(
        RetrievalCapacityExceededError,
        match="Cannot fit required subject conflict disclosure",
    ):
        planner.plan_evidence(
            version_id=scope.architecture_version_id,
            project_id=scope.project_id,
            facts=[fact],
            relationships=[],
            include_conflicts=True,
        )


def test_evidence_planner_budget_truncation_emits_omission():
    """Verify evidence truncation at max_evidence emits an omission summary."""
    scope = _make_scope()
    port = MockCanonicalPort(scope)
    policy = RetrievalPolicy()

    evs = [
        EvidenceItemView(
            record_id=uuid4(),
            logical_id=f"ev_{i:02d}",
            source_record_type="ast",
            path=f"src/file_{i}.py",
            polarity="supporting",
            strength="direct_source",
        )
        for i in range(10)
    ]
    port.evidence = evs

    fact = CanonicalFactView(
        record_id=uuid4(),
        logical_id="ent_bulk",
        kind="service",
        name="BulkService",
        status="confirmed",
        evidence_references=tuple(e.logical_id for e in evs),
    )

    planner = EvidencePlanner(canonical_port=port, policy=policy)
    res = planner.plan_evidence(
        version_id=scope.architecture_version_id,
        project_id=scope.project_id,
        facts=[fact],
        relationships=[],
        max_evidence=3,
    )

    assert len(res.evidence) == 3
    omission = next(o for o in res.omissions if o.reason == "evidence_budget_exceeded")
    assert omission.omitted_count == 7
    assert omission.details.get("requested_limit") == 3
