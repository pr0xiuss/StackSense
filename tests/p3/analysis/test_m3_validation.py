"""Validation tests for Phase 3 Module 3 (Intermediate Representation).

Verifies IRValidator enforcement of schema versions, key uniqueness,
referential integrity, completeness accounting, and numeric resource boundaries.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.platform.analysis.domain.constants import (
    ANALYZER_VERSION,
    IR_SCHEMA_VERSION,
)
from backend.platform.analysis.ir import (
    IRCapacityConfig,
    IRCapacityLimitError,
    IRCompleteness,
    IRConflict,
    IRDocument,
    IREntity,
    IREntityKind,
    IREvidence,
    IREvidenceStrength,
    IRRelationship,
    IRRelationshipKind,
    IRUnresolvedReason,
    IRUnresolvedReference,
    IRValidationError,
    IRValidator,
    build_entity_key,
    build_evidence_key,
    build_relationship_key,
)


def _make_test_doc(
    entities: tuple[IREntity, ...] = (),
    relationships: tuple[IRRelationship, ...] = (),
    evidence: tuple[IREvidence, ...] = (),
    unresolved: tuple[IRUnresolvedReference, ...] = (),
    conflicts: tuple[IRConflict, ...] = (),
    is_partial: bool = False,
    failed_artifacts: int = 0,
    ir_schema_version: str = IR_SCHEMA_VERSION,
    f2_version: str = "1.0.0",
    analyzer_version: str = ANALYZER_VERSION,
    analysis_id: UUID | None = None,
    project_id: UUID | None = None,
    repository_id: UUID | None = None,
    snapshot_id: UUID | None = None,
    config_fingerprint: str = "cfg-valid",
) -> IRDocument:
    """Helper creating a structurally valid test IRDocument."""
    a_id = analysis_id or uuid4()
    p_id = project_id or uuid4()
    r_id = repository_id or uuid4()
    s_id = snapshot_id or uuid4()

    repo_key = build_entity_key(IREntityKind.REPOSITORY, f"repo-{r_id}")
    snap_key = build_entity_key(IREntityKind.SNAPSHOT, f"snap-{s_id}")
    root_ev_key = build_evidence_key("root", "root", None)

    base_ev = IREvidence(
        evidence_key=root_ev_key,
        artifact_id=None,
        path="root",
        source_record_type="root",
        strength=IREvidenceStrength.CONFIGURATION,
    )
    base_repo = IREntity(
        ir_key=repo_key,
        kind=IREntityKind.REPOSITORY,
        name=f"repo-{r_id}",
        evidence_keys=(root_ev_key,),
    )
    base_snap = IREntity(
        ir_key=snap_key,
        kind=IREntityKind.SNAPSHOT,
        name=f"snap-{s_id}",
        evidence_keys=(root_ev_key,),
    )
    base_rel = IRRelationship(
        ir_key=build_relationship_key(IRRelationshipKind.CONTAINS, repo_key, snap_key),
        kind=IRRelationshipKind.CONTAINS,
        source_key=repo_key,
        target_key=snap_key,
        evidence_keys=(root_ev_key,),
    )

    all_ev = (base_ev, *evidence)
    all_ent = (base_repo, base_snap, *entities)
    all_rel = (base_rel, *relationships)

    return IRDocument(
        analysis_id=a_id,
        project_id=p_id,
        repository_id=r_id,
        snapshot_id=s_id,
        configuration_fingerprint=config_fingerprint,
        entities=all_ent,
        relationships=all_rel,
        evidence=all_ev,
        unresolved_references=unresolved,
        conflicts=conflicts,
        completeness=IRCompleteness(
            total_inventory_artifacts=len(all_ent),
            analyzed_artifacts=len(all_ent),
            failed_artifacts=failed_artifacts,
            total_entities=len(all_ent),
            total_relationships=len(all_rel),
            total_unresolved_references=len(unresolved),
            total_conflicts=len(conflicts),
            is_partial=is_partial or (failed_artifacts > 0),
        ),
        ir_schema_version=ir_schema_version,
        f2_version=f2_version,
        analyzer_version=analyzer_version,
    )


class TestIRValidatorSchemaInvariants:
    """Tests schema and version invariants."""

    def test_valid_document_passes_validation(self) -> None:
        validator = IRValidator()
        doc = _make_test_doc()
        validator.validate(doc)

    def test_reject_unsupported_schema_version(self) -> None:
        validator = IRValidator()
        doc = _make_test_doc()
        object.__setattr__(doc, "ir_schema_version", "2.0.0")
        with pytest.raises(IRValidationError, match="Unsupported IR schema version"):
            validator.validate(doc)

    def test_reject_unsupported_f2_version(self) -> None:
        validator = IRValidator()
        doc = _make_test_doc()
        object.__setattr__(doc, "f2_version", "2.0.0")
        with pytest.raises(IRValidationError, match="Unsupported F2 contract version"):
            validator.validate(doc)

    def test_reject_unsupported_analyzer_version(self) -> None:
        validator = IRValidator()
        doc = _make_test_doc(analyzer_version="9.9.9")
        with pytest.raises(IRValidationError, match="Unsupported analyzer version"):
            validator.validate(doc)

    def test_reject_non_irdocument_type(self) -> None:
        validator = IRValidator()
        with pytest.raises(IRValidationError, match="Expected IRDocument"):
            validator.validate("not-a-doc")  # type: ignore[arg-type]


class TestIRValidatorCompletenessInvariants:
    """Tests completeness accounting invariants."""

    def test_reject_counter_mismatch(self) -> None:
        validator = IRValidator()
        doc = _make_test_doc()
        # Corrupt completeness counter
        bad_completeness = IRCompleteness(
            total_entities=len(doc.entities) + 5,
            total_relationships=len(doc.relationships),
            total_unresolved_references=len(doc.unresolved_references),
            total_conflicts=len(doc.conflicts),
            is_partial=False,
        )
        object.__setattr__(doc, "completeness", bad_completeness)

        with pytest.raises(IRValidationError, match="does not match actual entities"):
            validator.validate(doc)

    def test_reject_failed_artifacts_without_partial_flag(self) -> None:
        validator = IRValidator()
        doc = _make_test_doc()
        bad_completeness = IRCompleteness(
            total_entities=len(doc.entities),
            total_relationships=len(doc.relationships),
            total_unresolved_references=len(doc.unresolved_references),
            total_conflicts=len(doc.conflicts),
            failed_artifacts=2,
            is_partial=False,  # Inconsistent: failed_artifacts > 0 must be partial
        )
        object.__setattr__(doc, "completeness", bad_completeness)

        with pytest.raises(
            IRValidationError, match="failed artifacts but is_partial is False"
        ):
            validator.validate(doc)


class TestIRValidatorCapacityLimits:
    """Tests enforcement of numeric resource caps."""

    def test_entity_cap_exceeded_raises_capacity_error(self) -> None:
        caps = IRCapacityConfig(max_entities=2)
        validator = IRValidator(caps=caps)
        # Default doc has 2 entities (repo + snap)
        doc = _make_test_doc()
        # Add 1 more entity to exceed cap
        ev_key = doc.evidence[0].evidence_key
        extra_ent = IREntity(
            ir_key="symbol::src/a.py::f",
            kind=IREntityKind.SYMBOL,
            name="f",
            evidence_keys=(ev_key,),
        )
        doc_over = _make_test_doc(entities=(extra_ent,))

        with pytest.raises(IRCapacityLimitError, match="Entity count .* exceeds cap"):
            validator.validate(doc_over)

    def test_relationship_cap_exceeded_raises_capacity_error(self) -> None:
        caps = IRCapacityConfig(max_relationships=1)
        validator = IRValidator(caps=caps)
        fixed_repo_id = uuid4()
        repo_key = build_entity_key(IREntityKind.REPOSITORY, f"repo-{fixed_repo_id}")
        root_ev_key = build_evidence_key("root", "root", None)
        extra_rel = IRRelationship(
            ir_key="rel::declares_dependency::repo::none::dep",
            kind=IRRelationshipKind.DECLARES_DEPENDENCY,
            source_key=repo_key,
            evidence_keys=(root_ev_key,),
            metadata={"dependency_name": "foo"},
        )
        doc_over = _make_test_doc(
            repository_id=fixed_repo_id,
            relationships=(extra_rel,),
        )

        with pytest.raises(
            IRCapacityLimitError, match="Relationship count .* exceeds cap"
        ):
            validator.validate(doc_over)

    def test_evidence_cap_exceeded_raises_capacity_error(self) -> None:
        caps = IRCapacityConfig(max_evidence=1)
        validator = IRValidator(caps=caps)
        # Default doc has 1 evidence
        extra_ev = IREvidence(
            evidence_key="ev::extra",
            artifact_id=None,
            path="src/b.py",
            source_record_type="test",
            strength=IREvidenceStrength.DIRECT_SOURCE,
        )
        doc_over = _make_test_doc(evidence=(extra_ev,))

        with pytest.raises(IRCapacityLimitError, match="Evidence count .* exceeds cap"):
            validator.validate(doc_over)

    def test_unresolved_cap_exceeded_raises_capacity_error(self) -> None:
        caps = IRCapacityConfig(max_unresolved_references=0)
        validator = IRValidator(caps=caps)
        fixed_repo_id = uuid4()
        repo_key = build_entity_key(IREntityKind.REPOSITORY, f"repo-{fixed_repo_id}")
        root_ev_key = build_evidence_key("root", "root", None)
        unres = IRUnresolvedReference(
            unresolved_key="unres::1",
            source_key=repo_key,
            relationship_kind=IRRelationshipKind.IMPORTS,
            target_name="missing_pkg",
            reason=IRUnresolvedReason.NOT_FOUND,
            evidence_keys=(root_ev_key,),
        )
        doc_over = _make_test_doc(
            repository_id=fixed_repo_id,
            unresolved=(unres,),
        )

        with pytest.raises(
            IRCapacityLimitError, match="Unresolved reference count .* exceeds cap"
        ):
            validator.validate(doc_over)

    def test_conflict_cap_exceeded_raises_capacity_error(self) -> None:
        caps = IRCapacityConfig(max_conflicts=0)
        validator = IRValidator(caps=caps)
        doc = _make_test_doc()
        ev_key = doc.evidence[0].evidence_key
        conflict = IRConflict(
            conflict_key="conflict::1",
            conflict_type="semantic",
            subject_key=doc.entities[0].ir_key,
            competing_evidence_keys=(ev_key,),
        )
        doc_over = _make_test_doc(conflicts=(conflict,))

        with pytest.raises(IRCapacityLimitError, match="Conflict count .* exceeds cap"):
            validator.validate(doc_over)

    def test_serialized_bytes_cap_exceeded_raises_capacity_error(self) -> None:
        # Set payload byte cap very small (100 bytes)
        caps = IRCapacityConfig(max_serialized_bytes=100)
        validator = IRValidator(caps=caps)
        doc = _make_test_doc()

        with pytest.raises(IRCapacityLimitError, match="payload size .* exceeds cap"):
            validator.validate(doc)
