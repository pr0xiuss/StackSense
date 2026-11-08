"""M4 Batch 2 construction, semantic relationship, and golden tests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from backend.platform.analysis.architecture import (
    ArchitectureBuilder,
    ArchitectureCapacityConfig,
    ArchitectureEntityKind,
    ArchitectureFactStatus,
    ArchitectureRelationshipKind,
    ArchitectureUnresolvedReason,
    ArchitectureValidator,
)
from backend.platform.analysis.ir import (
    IRCompleteness,
    IRConflict,
    IRDocument,
    IREntity,
    IREntityKind,
    IREvidence,
    IREvidenceStrength,
    IRFactStatus,
    IRRelationship,
    IRRelationshipKind,
    IRUnresolvedReason,
    IRUnresolvedReference,
)

ANALYSIS_ID = UUID("10000000-0000-0000-0000-000000000001")
PROJECT_ID = UUID("20000000-0000-0000-0000-000000000002")
REPOSITORY_ID = UUID("30000000-0000-0000-0000-000000000003")
SNAPSHOT_ID = UUID("40000000-0000-0000-0000-000000000004")
VERSION_ID = UUID("50000000-0000-0000-0000-000000000005")
GOLDENS = json.loads(
    (
        Path(__file__).parents[2] / "fixtures" / "p3" / "m4" / "framework_goldens.json"
    ).read_text(encoding="utf-8")
)


def _capacity(**overrides: int) -> ArchitectureCapacityConfig:
    values = {
        "max_entities": 1_000,
        "max_relationships": 2_000,
        "max_evidence": 3_000,
        "max_unresolved_relationships": 1_000,
        "max_conflicts": 1_000,
        "max_serialized_bytes": 10_000_000,
    }
    values.update(overrides)
    return ArchitectureCapacityConfig(**values)


def _builder(**capacity_overrides: int) -> ArchitectureBuilder:
    return ArchitectureBuilder(ArchitectureValidator(_capacity(**capacity_overrides)))


def _evidence(
    key: str,
    *,
    source_record_type: str = "declaration_fact",
    framework: str | None = None,
    metadata: dict[str, object] | None = None,
) -> IREvidence:
    return IREvidence(
        evidence_key=key,
        artifact_id=None,
        path="src/app.py" if source_record_type != "framework_detection" else "root",
        source_record_type=source_record_type,
        source_fact_key=key if source_record_type != "framework_detection" else None,
        framework_name=framework,
        strength=(
            IREvidenceStrength.FRAMEWORK_STRUCTURAL
            if framework
            else IREvidenceStrength.DIRECT_SOURCE
        ),
        metadata=metadata or {},
    )


def _component(
    key: str,
    evidence_key: str,
    *,
    qualified_name: str,
    role: str,
) -> IREntity:
    return IREntity(
        ir_key=key,
        kind=IREntityKind.COMPONENT,
        name=qualified_name.rsplit(".", maxsplit=1)[-1],
        qualified_name=qualified_name,
        framework="fastapi",
        evidence_keys=(evidence_key,),
        metadata={"architectural_role": role, "application_namespace": "api"},
    )


def _document(
    *,
    entities: tuple[IREntity, ...],
    evidence: tuple[IREvidence, ...],
    relationships: tuple[IRRelationship, ...] = (),
    unresolved: tuple[IRUnresolvedReference, ...] = (),
    conflicts: tuple[IRConflict, ...] = (),
    partial: bool = False,
) -> IRDocument:
    return IRDocument(
        analysis_id=ANALYSIS_ID,
        project_id=PROJECT_ID,
        repository_id=REPOSITORY_ID,
        snapshot_id=SNAPSHOT_ID,
        configuration_fingerprint="cfg",
        entities=entities,
        relationships=relationships,
        evidence=evidence,
        unresolved_references=unresolved,
        conflicts=conflicts,
        completeness=IRCompleteness(
            total_inventory_artifacts=4,
            analyzed_artifacts=3,
            failed_artifacts=1 if partial else 0,
            total_syntax_documents=2,
            total_syntax_facts=len(evidence),
            total_entities=len(entities),
            total_relationships=len(relationships),
            total_unresolved_references=len(unresolved),
            total_conflicts=len(conflicts),
            is_partial=partial,
        ),
    )


@pytest.mark.parametrize(
    ("framework", "expected_kind"),
    [
        (item["framework"], ArchitectureEntityKind(item["entity_kind"]))
        for item in GOLDENS
    ],
)
def test_confirmed_framework_root_promotes_supported_application(
    framework: str, expected_kind: ArchitectureEntityKind
) -> None:
    framework_evidence = _evidence(
        f"framework-{framework}",
        source_record_type="framework_detection",
        metadata={
            "framework": framework,
            "status": "confirmed",
            "signals": (f"syntax_import:{framework}",),
        },
    )

    model = (
        _builder()
        .build(_document(entities=(), evidence=(framework_evidence,)), VERSION_ID)
        .document
    )

    assert len(model.entities) == 1
    assert model.entities[0].kind == expected_kind
    assert model.entities[0].status == ArchitectureFactStatus.SUPPORTED
    assert model.entities[0].metadata["framework"] == framework


def test_framework_candidate_without_confirmed_structure_is_not_promoted() -> None:
    candidate = _evidence(
        "framework-express",
        source_record_type="framework_detection",
        metadata={"framework": "express", "status": "supported"},
    )

    model = (
        _builder()
        .build(_document(entities=(), evidence=(candidate,)), VERSION_ID)
        .document
    )

    assert model.entities == ()
    assert model.evidence == ()


def test_evidence_preserves_actual_producer_fields_without_raw_source_literals() -> (
    None
):
    evidence = _evidence(
        "declaration",
        metadata={
            "declaration_kind": "class",
            "decorators": ("router",),
            "signature_text": "def handler(secret='literal')",
            "unapproved_field": "discarded",
        },
    )
    component = _component(
        "component",
        evidence.evidence_key,
        qualified_name="api.Handler",
        role="controller",
    )

    model = (
        _builder()
        .build(_document(entities=(component,), evidence=(evidence,)), VERSION_ID)
        .document
    )
    mapped = model.evidence[0]

    assert mapped.source_record_type == "declaration_fact"
    assert mapped.source_fact_key == "declaration"
    assert mapped.metadata["declaration_kind"] == "class"
    assert mapped.metadata["decorators"] == ("router",)
    assert "signature_text" not in mapped.metadata
    assert "unapproved_field" not in mapped.metadata


def test_competing_evidence_marks_promoted_fact_conflicting() -> None:
    evidence = replace(_evidence("conflicting"), polarity="conflicting")
    component = _component(
        "component",
        evidence.evidence_key,
        qualified_name="api.Handler",
        role="controller",
    )

    model = (
        _builder()
        .build(_document(entities=(component,), evidence=(evidence,)), VERSION_ID)
        .document
    )

    assert model.entities[0].status == ArchitectureFactStatus.CONFLICTING
    assert model.evidence[0].polarity.value == "conflicting"


def test_application_scope_exposes_endpoint_and_routes_to_exact_handler() -> None:
    framework_evidence = _evidence(
        "framework-fastapi",
        source_record_type="framework_detection",
        metadata={"framework": "fastapi", "status": "confirmed"},
    )
    handler_evidence = _evidence("handler")
    route_evidence = _evidence("route", framework="fastapi")
    handler = replace(
        _component(
            "handler-ir",
            "handler",
            qualified_name="api.users.list_users",
            role="controller",
        ),
        metadata={"architectural_role": "controller"},
    )
    endpoint = IREntity(
        ir_key="endpoint-ir",
        kind=IREntityKind.ENDPOINT,
        name="list users",
        qualified_name="api.users.list_users",
        framework="fastapi",
        status=IRFactStatus.INFERRED,
        evidence_keys=(route_evidence.evidence_key,),
        metadata={"method": "GET", "path": "/users"},
    )

    model = (
        _builder()
        .build(
            _document(
                entities=(handler, endpoint),
                evidence=(framework_evidence, handler_evidence, route_evidence),
            ),
            VERSION_ID,
        )
        .document
    )

    assert {entity.kind for entity in model.entities} == {
        ArchitectureEntityKind.APPLICATION,
        ArchitectureEntityKind.CONTROLLER,
        ArchitectureEntityKind.ENDPOINT,
    }
    assert {relationship.kind for relationship in model.relationships} == {
        ArchitectureRelationshipKind.CONTAINS,
        ArchitectureRelationshipKind.EXPOSES,
        ArchitectureRelationshipKind.ROUTES_TO,
    }


def test_static_relationships_are_precise_and_repeated_evidence_merges() -> None:
    first_evidence = _evidence("caller-a")
    second_evidence = _evidence("caller-b")
    target_evidence = _evidence("target")
    caller = _component(
        "caller", "caller-a", qualified_name="api.UsersController", role="controller"
    )
    target = _component(
        "target", "target", qualified_name="api.UsersService", role="service"
    )
    first = IRRelationship(
        ir_key="call-a",
        kind=IRRelationshipKind.STATIC_CALL_REFERENCE,
        source_key=caller.ir_key,
        target_key=target.ir_key,
        evidence_keys=(first_evidence.evidence_key,),
    )
    second = replace(
        first, ir_key="call-b", evidence_keys=(second_evidence.evidence_key,)
    )

    model = (
        _builder()
        .build(
            _document(
                entities=(caller, target),
                evidence=(first_evidence, second_evidence, target_evidence),
                relationships=(first, second),
            ),
            VERSION_ID,
        )
        .document
    )

    calls = [
        item
        for item in model.relationships
        if item.kind == ArchitectureRelationshipKind.CALLS
    ]
    assert len(calls) == 1
    assert calls[0].status == ArchitectureFactStatus.SUPPORTED
    assert len(calls[0].evidence_ids) == 2
    assert "runtime" not in calls[0].metadata


def test_infrastructure_promotion_and_dependency_semantics_are_precise() -> None:
    keys = ("service", "database", "external", "queue", "config", "library")
    evidence = tuple(_evidence(key) for key in keys)
    service = _component(
        "service", "service", qualified_name="api.Service", role="service"
    )
    database = IREntity(
        ir_key="database",
        kind=IREntityKind.DATABASE,
        name="PostgreSQL",
        evidence_keys=("database",),
        metadata={
            "database_engine": "postgresql",
            "application_namespace": "api",
            "usage_evidence": True,
        },
    )
    external = IREntity(
        ir_key="external",
        kind=IREntityKind.EXTERNAL_SYSTEM,
        name="Stripe",
        evidence_keys=("external",),
        metadata={
            "external_kind": "service",
            "identity_anchor": "stripe",
            "application_namespace": "api",
            "usage_evidence": True,
        },
    )
    queue = IREntity(
        ir_key="queue",
        kind=IREntityKind.MESSAGE_INFRASTRUCTURE,
        name="orders",
        evidence_keys=("queue",),
        metadata={
            "infrastructure_kind": "queue",
            "identity_anchor": "orders",
            "application_namespace": "api",
            "usage_evidence": True,
        },
    )
    configuration = IREntity(
        ir_key="config",
        kind=IREntityKind.CONFIGURATION,
        name="Runtime configuration",
        evidence_keys=("config",),
        metadata={
            "identity_anchor": "runtime",
            "application_namespace": "api",
            "architecture_effect": True,
        },
    )
    library = replace(
        _component("library", "library", qualified_name="shared.auth", role="library"),
        metadata={
            "architectural_role": "library",
            "application_namespace": "api",
            "manifest_declared": True,
            "source_referenced": True,
        },
    )
    targets = (database, external, queue, configuration, library)
    relationships = tuple(
        IRRelationship(
            ir_key=f"dependency-{target.ir_key}",
            kind=IRRelationshipKind.SOURCE_REFERENCES_DEPENDENCY,
            source_key=service.ir_key,
            target_key=target.ir_key,
            evidence_keys=(target.evidence_keys[0],),
            metadata=(
                {"messaging_action": "produce"} if target.ir_key == "queue" else {}
            ),
        )
        for target in targets
    )

    model = (
        _builder()
        .build(
            _document(
                entities=(service, *targets),
                evidence=evidence,
                relationships=relationships,
            ),
            VERSION_ID,
        )
        .document
    )

    assert {entity.kind for entity in model.entities} == {
        ArchitectureEntityKind.SERVICE,
        ArchitectureEntityKind.DATABASE,
        ArchitectureEntityKind.EXTERNAL_SERVICE,
        ArchitectureEntityKind.QUEUE,
        ArchitectureEntityKind.CONFIGURATION_COMPONENT,
        ArchitectureEntityKind.LIBRARY,
    }
    assert {relationship.kind for relationship in model.relationships} == {
        ArchitectureRelationshipKind.PERSISTS_TO,
        ArchitectureRelationshipKind.CONNECTS_TO,
        ArchitectureRelationshipKind.PRODUCES,
        ArchitectureRelationshipKind.USES,
    }


def test_name_only_infrastructure_and_unreferenced_library_are_not_promoted() -> None:
    database_evidence = _evidence("database")
    library_evidence = _evidence("library")
    database = IREntity(
        ir_key="database",
        kind=IREntityKind.DATABASE,
        name="PostgreSQL",
        evidence_keys=(database_evidence.evidence_key,),
        metadata={"database_engine": "postgresql"},
    )
    library = _component(
        "library", "library", qualified_name="shared.auth", role="library"
    )

    model = (
        _builder()
        .build(
            _document(
                entities=(database, library),
                evidence=(database_evidence, library_evidence),
            ),
            VERSION_ID,
        )
        .document
    )

    assert model.entities == ()


def test_unresolved_and_conflicting_f3_records_survive_with_provenance() -> None:
    source_evidence = _evidence("source")
    conflict_evidence = _evidence("conflict")
    source = _component(
        "source-ir",
        "source",
        qualified_name="api.UsersController",
        role="controller",
    )
    unresolved = IRUnresolvedReference(
        unresolved_key="missing-service",
        source_key=source.ir_key,
        relationship_kind=IRRelationshipKind.STATIC_CALL_REFERENCE,
        target_name="UsersService",
        reason=IRUnresolvedReason.NOT_FOUND,
        candidate_references=("api.UsersService",),
        evidence_keys=(source_evidence.evidence_key,),
    )
    relationship = IRRelationship(
        ir_key="unresolved-call",
        kind=IRRelationshipKind.STATIC_CALL_REFERENCE,
        source_key=source.ir_key,
        unresolved_reference_key=unresolved.unresolved_key,
        status=IRFactStatus.UNRESOLVED,
        evidence_keys=(source_evidence.evidence_key,),
    )
    conflict = IRConflict(
        conflict_key="framework-conflict",
        conflict_type="framework",
        subject_key=source.ir_key,
        competing_evidence_keys=(conflict_evidence.evidence_key,),
        details={"frameworks": ("flask", "fastapi")},
    )

    model = (
        _builder()
        .build(
            _document(
                entities=(source,),
                evidence=(source_evidence, conflict_evidence),
                relationships=(relationship,),
                unresolved=(unresolved,),
                conflicts=(conflict,),
                partial=True,
            ),
            VERSION_ID,
        )
        .document
    )

    assert len(model.unresolved_relationships) == 1
    assert (
        model.unresolved_relationships[0].reason
        == ArchitectureUnresolvedReason.NOT_FOUND
    )
    assert len(model.conflicts) == 1
    assert model.conflicts[0].conflict_type == "framework"
    assert model.completeness.is_partial is True
    assert model.completeness.failed_artifacts == 1


def test_model_digest_and_content_are_order_independent() -> None:
    first = _evidence("first")
    second = _evidence("second")
    entities = (
        _component("one", "first", qualified_name="api.One", role="service"),
        _component("two", "second", qualified_name="api.Two", role="service"),
    )

    forward = (
        _builder()
        .build(_document(entities=entities, evidence=(first, second)), VERSION_ID)
        .document
    )
    reverse = (
        _builder()
        .build(
            _document(
                entities=tuple(reversed(entities)),
                evidence=tuple(reversed((first, second))),
            ),
            UUID("50000000-0000-0000-0000-000000000099"),
        )
        .document
    )

    assert forward.content_digest == reverse.content_digest
    assert forward.semantic_payload() == reverse.semantic_payload()
    assert forward.architecture_version_id != reverse.architecture_version_id
