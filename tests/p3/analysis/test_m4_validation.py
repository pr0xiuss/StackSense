"""M4 Batch 2 whole-model validation and capacity regression tests."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from backend.platform.analysis.architecture import (
    ArchitectureBuilder,
    ArchitectureCapacityConfig,
    ArchitectureCapacityError,
    ArchitectureRelationship,
    ArchitectureRelationshipKind,
    ArchitectureValidationError,
    ArchitectureValidator,
    ValidatedArchitectureModel,
    build_relationship_logical_id,
)
from backend.platform.analysis.ir import (
    IRCompleteness,
    IRConflict,
    IRDocument,
    IREntity,
    IREntityKind,
    IREvidence,
    IRFactStatus,
    IRRelationship,
    IRRelationshipKind,
    IRUnresolvedReason,
    IRUnresolvedReference,
)

ANALYSIS_ID = UUID("61000000-0000-0000-0000-000000000001")
PROJECT_ID = UUID("62000000-0000-0000-0000-000000000002")
REPOSITORY_ID = UUID("63000000-0000-0000-0000-000000000003")
SNAPSHOT_ID = UUID("64000000-0000-0000-0000-000000000004")
VERSION_ID = UUID("65000000-0000-0000-0000-000000000005")


def _capacity(**overrides: int) -> ArchitectureCapacityConfig:
    values = {
        "max_entities": 100,
        "max_relationships": 100,
        "max_evidence": 100,
        "max_unresolved_relationships": 100,
        "max_conflicts": 100,
        "max_serialized_bytes": 1_000_000,
    }
    values.update(overrides)
    return ArchitectureCapacityConfig(**values)


def _source(count: int = 2) -> IRDocument:
    evidence = tuple(
        IREvidence(
            evidence_key=f"evidence-{index}",
            artifact_id=None,
            path=f"src/service_{index}.py",
            source_record_type="declaration_fact",
            source_fact_key=f"fact-{index}",
        )
        for index in range(count)
    )
    entities = tuple(
        IREntity(
            ir_key=f"service-{index}",
            kind=IREntityKind.COMPONENT,
            name=f"Service{index}",
            qualified_name=f"api.Service{index}",
            framework="fastapi",
            evidence_keys=(f"evidence-{index}",),
            metadata={
                "application_namespace": "api",
                "architectural_role": "service",
            },
        )
        for index in range(count)
    )
    return IRDocument(
        analysis_id=ANALYSIS_ID,
        project_id=PROJECT_ID,
        repository_id=REPOSITORY_ID,
        snapshot_id=SNAPSHOT_ID,
        configuration_fingerprint="cfg",
        entities=entities,
        relationships=(),
        evidence=evidence,
        unresolved_references=(),
        conflicts=(),
        completeness=IRCompleteness(
            total_entities=count,
            total_syntax_facts=count,
        ),
    )


def _build(count: int = 2) -> ValidatedArchitectureModel:
    validator = ArchitectureValidator(_capacity())
    return ArchitectureBuilder(validator).build(_source(count), VERSION_ID)


def test_capacity_config_requires_explicit_positive_values() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        _capacity(max_entities=0)


def test_approved_production_capacity_defaults_are_enforced() -> None:
    capacity = ArchitectureCapacityConfig()

    assert capacity.max_entities == 25_000
    assert capacity.max_relationships == 50_000
    assert capacity.max_evidence == 75_000
    assert capacity.max_unresolved_relationships == 10_000
    assert capacity.max_conflicts == 5_000
    assert capacity.max_serialized_bytes == 128 * 1024 * 1024


def test_entity_and_serialized_capacity_limits_fail_without_truncation() -> None:
    with pytest.raises(ArchitectureCapacityError) as entity_error:
        ArchitectureBuilder(ArchitectureValidator(_capacity(max_entities=1))).build(
            _source(), VERSION_ID
        )
    assert entity_error.value.code == "architecture_capacity_exceeded"
    assert entity_error.value.diagnostic_details == {
        "dimension": "entities",
        "actual": 2,
        "limit": 1,
    }

    with pytest.raises(ArchitectureCapacityError) as payload_error:
        ArchitectureBuilder(
            ArchitectureValidator(_capacity(max_serialized_bytes=10))
        ).build(_source(1), VERSION_ID)
    assert payload_error.value.diagnostic_details["dimension"] == (
        "canonical_payload_bytes"
    )


def test_all_collection_capacity_limits_are_enforced() -> None:
    source = _source(3)
    resolved_relationships = tuple(
        IRRelationship(
            ir_key=f"call-{index}",
            kind=IRRelationshipKind.STATIC_CALL_REFERENCE,
            source_key=f"service-{index}",
            target_key=f"service-{index + 1}",
            evidence_keys=(f"evidence-{index}",),
        )
        for index in range(2)
    )
    unresolved = tuple(
        IRUnresolvedReference(
            unresolved_key=f"unresolved-{index}",
            source_key=f"service-{index}",
            relationship_kind=IRRelationshipKind.STATIC_CALL_REFERENCE,
            target_name=f"Dynamic{index}",
            reason=IRUnresolvedReason.DYNAMIC,
            evidence_keys=(f"evidence-{index}",),
        )
        for index in range(2)
    )
    unresolved_relationships = tuple(
        IRRelationship(
            ir_key=f"dynamic-{index}",
            kind=IRRelationshipKind.STATIC_CALL_REFERENCE,
            source_key=f"service-{index}",
            unresolved_reference_key=f"unresolved-{index}",
            status=IRFactStatus.UNRESOLVED,
            evidence_keys=(f"evidence-{index}",),
        )
        for index in range(2)
    )
    conflicts = tuple(
        IRConflict(
            conflict_key=f"conflict-{index}",
            conflict_type="test",
            subject_key=f"service-{index}",
            competing_evidence_keys=(f"evidence-{index}",),
        )
        for index in range(2)
    )
    dense_source = replace(
        source,
        relationships=resolved_relationships + unresolved_relationships,
        unresolved_references=unresolved,
        conflicts=conflicts,
        completeness=replace(
            source.completeness,
            total_relationships=4,
            total_unresolved_references=2,
            total_conflicts=2,
        ),
    )
    document = (
        ArchitectureBuilder(ArchitectureValidator(_capacity()))
        .build(dense_source, VERSION_ID)
        .document
    )

    limit_cases = (
        ("relationships", {"max_relationships": 1}),
        ("evidence", {"max_evidence": 1}),
        ("unresolved relationships", {"max_unresolved_relationships": 1}),
        ("conflicts", {"max_conflicts": 1}),
    )
    for expected, override in limit_cases:
        with pytest.raises(ArchitectureCapacityError, match=expected):
            ArchitectureValidator(_capacity(**override)).validate(document)


def test_builder_returns_only_whole_model_validation_marker() -> None:
    result = _build()
    assert isinstance(result, ValidatedArchitectureModel)
    assert result.document.content_digest


def test_invalid_relationship_direction_is_rejected() -> None:
    model = _build().document
    source, target = model.entities
    invalid = ArchitectureRelationship(
        logical_id=build_relationship_logical_id(
            project_id=PROJECT_ID,
            repository_id=REPOSITORY_ID,
            kind=ArchitectureRelationshipKind.PERSISTS_TO,
            source_logical_id=source.logical_id,
            target_logical_id=target.logical_id,
        ),
        kind=ArchitectureRelationshipKind.PERSISTS_TO,
        source_logical_id=source.logical_id,
        target_logical_id=target.logical_id,
        status=source.status,
        evidence_ids=source.evidence_ids,
        source_ir_keys=source.source_ir_keys,
    )
    candidate = replace(
        model,
        relationships=(invalid,),
        completeness=replace(model.completeness, architecture_relationships=1),
        content_digest="",
    )

    with pytest.raises(ArchitectureValidationError, match="target kind"):
        ArchitectureValidator(_capacity()).validate(candidate)


def test_missing_relationship_endpoint_and_evidence_are_rejected() -> None:
    model = _build(1).document
    source = model.entities[0]
    relationship = ArchitectureRelationship(
        logical_id=build_relationship_logical_id(
            project_id=PROJECT_ID,
            repository_id=REPOSITORY_ID,
            kind=ArchitectureRelationshipKind.DEPENDS_ON,
            source_logical_id=source.logical_id,
            target_logical_id="architecture://missing",
        ),
        kind=ArchitectureRelationshipKind.DEPENDS_ON,
        source_logical_id=source.logical_id,
        target_logical_id="architecture://missing",
        status=source.status,
        evidence_ids=("evidence://missing",),
        source_ir_keys=source.source_ir_keys,
    )
    candidate = replace(
        model,
        relationships=(relationship,),
        completeness=replace(model.completeness, architecture_relationships=1),
        content_digest="",
    )

    with pytest.raises(ArchitectureValidationError, match="target is missing"):
        ArchitectureValidator(_capacity()).validate(candidate)


def test_containment_cycle_is_rejected_but_dependency_cycles_are_allowed() -> None:
    model = _build().document
    first, second = model.entities

    def relationship(
        kind: ArchitectureRelationshipKind, source: str, target: str
    ) -> ArchitectureRelationship:
        return ArchitectureRelationship(
            logical_id=build_relationship_logical_id(
                project_id=PROJECT_ID,
                repository_id=REPOSITORY_ID,
                kind=kind,
                source_logical_id=source,
                target_logical_id=target,
            ),
            kind=kind,
            source_logical_id=source,
            target_logical_id=target,
            status=first.status,
            evidence_ids=first.evidence_ids,
            source_ir_keys=first.source_ir_keys,
        )

    dependency_cycle = (
        relationship(
            ArchitectureRelationshipKind.DEPENDS_ON,
            first.logical_id,
            second.logical_id,
        ),
        relationship(
            ArchitectureRelationshipKind.DEPENDS_ON,
            second.logical_id,
            first.logical_id,
        ),
    )
    valid_cycle = replace(
        model,
        relationships=dependency_cycle,
        completeness=replace(model.completeness, architecture_relationships=2),
        content_digest="",
    )
    ArchitectureValidator(_capacity()).validate(valid_cycle)

    containment_cycle = tuple(
        replace(
            item,
            logical_id=build_relationship_logical_id(
                project_id=PROJECT_ID,
                repository_id=REPOSITORY_ID,
                kind=ArchitectureRelationshipKind.CONTAINS,
                source_logical_id=item.source_logical_id,
                target_logical_id=item.target_logical_id,
            ),
            kind=ArchitectureRelationshipKind.CONTAINS,
        )
        for item in dependency_cycle
    )
    invalid_cycle = replace(
        valid_cycle, relationships=containment_cycle, content_digest=""
    )
    with pytest.raises(ArchitectureValidationError, match="containment hierarchy"):
        ArchitectureValidator(_capacity()).validate(invalid_cycle)


def test_completeness_and_digest_mismatch_fail_closed() -> None:
    model = _build(1).document
    invalid_counts = replace(
        model,
        completeness=replace(model.completeness, architecture_entities=2),
        content_digest="",
    )
    with pytest.raises(ArchitectureValidationError, match="counts mismatch"):
        ArchitectureValidator(_capacity()).validate(invalid_counts)

    object.__setattr__(model, "content_digest", "0" * 64)
    with pytest.raises(ArchitectureValidationError, match="digest"):
        ArchitectureValidator(_capacity()).validate(model)
