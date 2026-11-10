"""Empirical M4 Batch 2 capacity evidence; values require owner approval."""

from __future__ import annotations

import time
import tracemalloc
from uuid import UUID

import pytest

from backend.platform.analysis.architecture import (
    ArchitectureBuilder,
    ArchitectureCapacityConfig,
    ArchitectureValidator,
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


@pytest.mark.slow
def test_promoted_architecture_capacity_benchmark() -> None:
    """Measure a dense 10k-entity promoted model without selecting final caps."""
    count = 10_000
    evidence = tuple(
        IREvidence(
            evidence_key=f"ev-{index}",
            artifact_id=None,
            path=f"src/components/component_{index}.py",
            source_record_type="declaration_fact",
            source_fact_key=f"fact-{index}",
        )
        for index in range(count)
    )
    entities = tuple(
        IREntity(
            ir_key=f"component-{index}",
            kind=IREntityKind.COMPONENT,
            name=f"Component{index}",
            qualified_name=f"app.components.Component{index}",
            framework="fastapi",
            evidence_keys=(f"ev-{index}",),
            metadata={
                "application_namespace": "benchmark",
                "architectural_role": "component",
            },
        )
        for index in range(count)
    )
    relationships = tuple(
        IRRelationship(
            ir_key=f"call-{index}",
            kind=IRRelationshipKind.STATIC_CALL_REFERENCE,
            source_key=f"component-{index}",
            target_key=f"component-{index + 1}",
            evidence_keys=(f"ev-{index}",),
        )
        for index in range(count - 1)
    )
    unresolved_count = count // 10
    unresolved = tuple(
        IRUnresolvedReference(
            unresolved_key=f"unresolved-{index}",
            source_key=f"component-{index}",
            relationship_kind=IRRelationshipKind.STATIC_CALL_REFERENCE,
            target_name=f"DynamicTarget{index}",
            reason=IRUnresolvedReason.DYNAMIC,
            evidence_keys=(f"ev-{index}",),
        )
        for index in range(unresolved_count)
    )
    unresolved_relationships = tuple(
        IRRelationship(
            ir_key=f"dynamic-call-{index}",
            kind=IRRelationshipKind.STATIC_CALL_REFERENCE,
            source_key=f"component-{index}",
            unresolved_reference_key=f"unresolved-{index}",
            status=IRFactStatus.UNRESOLVED,
            evidence_keys=(f"ev-{index}",),
        )
        for index in range(unresolved_count)
    )
    conflict_count = count // 100
    conflicts = tuple(
        IRConflict(
            conflict_key=f"conflict-{index}",
            conflict_type="benchmark_conflict",
            subject_key=f"component-{index}",
            competing_evidence_keys=(f"ev-{index}",),
        )
        for index in range(conflict_count)
    )
    source = IRDocument(
        analysis_id=UUID("71000000-0000-0000-0000-000000000001"),
        project_id=UUID("72000000-0000-0000-0000-000000000002"),
        repository_id=UUID("73000000-0000-0000-0000-000000000003"),
        snapshot_id=UUID("74000000-0000-0000-0000-000000000004"),
        configuration_fingerprint="benchmark",
        entities=entities,
        relationships=relationships + unresolved_relationships,
        evidence=evidence,
        unresolved_references=unresolved,
        conflicts=conflicts,
        completeness=IRCompleteness(
            total_entities=count,
            total_syntax_facts=count,
            total_relationships=len(relationships) + len(unresolved_relationships),
            total_unresolved_references=unresolved_count,
            total_conflicts=conflict_count,
        ),
    )
    capacity = ArchitectureCapacityConfig(
        max_entities=count,
        max_relationships=count * 2,
        max_evidence=count * 2,
        max_unresolved_relationships=count,
        max_conflicts=count,
        max_serialized_bytes=256 * 1024 * 1024,
    )
    tracemalloc.start()
    started = time.perf_counter()
    model = (
        ArchitectureBuilder(ArchitectureValidator(capacity))
        .build(source, UUID("75000000-0000-0000-0000-000000000005"))
        .document
    )
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    payload_bytes = len(model.to_canonical_json().encode("utf-8"))

    assert len(model.entities) == count
    assert len(model.relationships) == count - 1
    assert len(model.unresolved_relationships) == unresolved_count
    assert len(model.conflicts) == conflict_count
    assert elapsed < 60
    assert peak < 768 * 1024 * 1024
    assert payload_bytes < capacity.max_serialized_bytes
    print(
        "M4_BENCHMARK",
        f"entities={count}",
        f"relationships={len(model.relationships)}",
        f"unresolved={len(model.unresolved_relationships)}",
        f"conflicts={len(model.conflicts)}",
        f"seconds={elapsed:.3f}",
        f"peak_mib={peak / 1024 / 1024:.2f}",
        f"payload_mib={payload_bytes / 1024 / 1024:.2f}",
    )
