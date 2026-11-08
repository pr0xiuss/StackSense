"""M4 Batch 1 Architecture Model foundation contract tests."""

import math
from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from backend.platform.analysis.architecture import (
    ARCHITECTURE_SCHEMA_VERSION,
    ArchitectureEntity,
    ArchitectureEntityKind,
    ArchitectureEvidence,
    ArchitectureFactStatus,
    ArchitectureModelError,
    ArchitectureRelationshipKind,
    build_entity_logical_id,
    build_relationship_logical_id,
    encode_identity_component,
    normalize_route_path,
    semantic_signature,
)

PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
REPOSITORY_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_architecture_schema_and_vocabularies_are_exact() -> None:
    assert ARCHITECTURE_SCHEMA_VERSION == "1.0.0"
    assert {kind.value for kind in ArchitectureEntityKind} == {
        "application",
        "frontend_application",
        "service",
        "module",
        "component",
        "controller",
        "endpoint",
        "worker",
        "data_repository",
        "database",
        "message_broker",
        "queue",
        "topic",
        "external_service",
        "external_api",
        "library",
        "configuration_component",
        "unknown",
    }
    assert {kind.value for kind in ArchitectureRelationshipKind} == {
        "contains",
        "depends_on",
        "imports",
        "calls",
        "exposes",
        "consumes",
        "produces",
        "connects_to",
        "persists_to",
        "uses",
        "extends",
        "implements",
        "routes_to",
    }
    assert {status.value for status in ArchitectureFactStatus} == {
        "confirmed",
        "supported",
        "inferred",
        "unresolved",
        "conflicting",
    }


def test_identity_encoding_is_nfc_utf8_case_preserving_and_collision_safe() -> None:
    assert encode_identity_component("Cafe\u0301") == encode_identity_component("Café")
    assert encode_identity_component("Café") == "Caf%C3%A9"
    assert encode_identity_component("A") != encode_identity_component("a")
    assert encode_identity_component("a/b%20c") == "a%2Fb%2520c"
    assert encode_identity_component("a~b", compound=True) == "a%7Eb"


def test_entity_logical_id_has_project_repository_scope_and_no_raw_separator() -> None:
    logical_id = build_entity_logical_id(
        project_id=PROJECT_ID,
        repository_id=REPOSITORY_ID,
        kind=ArchitectureEntityKind.MODULE,
        namespace_parts=("api/app",),
        anchor_parts=("src/users",),
    )
    assert logical_id.startswith(
        "architecture://project/11111111-1111-1111-1111-111111111111/"
        "repository/22222222-2222-2222-2222-222222222222/module/"
    )
    assert "api%2Fapp" in logical_id
    assert "src%2Fusers" in logical_id


def test_required_identity_components_fail_closed() -> None:
    with pytest.raises(ArchitectureModelError, match="required"):
        build_entity_logical_id(
            project_id=PROJECT_ID,
            repository_id=REPOSITORY_ID,
            kind=ArchitectureEntityKind.MODULE,
            namespace_parts=(),
            anchor_parts=("users",),
        )
    with pytest.raises(ArchitectureModelError, match="must not be empty"):
        build_entity_logical_id(
            project_id=PROJECT_ID,
            repository_id=REPOSITORY_ID,
            kind=ArchitectureEntityKind.MODULE,
            namespace_parts=("",),
            anchor_parts=("users",),
        )


def test_relationship_id_requires_exactly_one_target_form() -> None:
    source = "architecture://source"
    target = "architecture://target"
    key = build_relationship_logical_id(
        project_id=PROJECT_ID,
        repository_id=REPOSITORY_ID,
        kind=ArchitectureRelationshipKind.DEPENDS_ON,
        source_logical_id=source,
        target_logical_id=target,
    )
    assert "/relationship/" in key
    with pytest.raises(ArchitectureModelError, match="exactly one"):
        build_relationship_logical_id(
            project_id=PROJECT_ID,
            repository_id=REPOSITORY_ID,
            kind=ArchitectureRelationshipKind.DEPENDS_ON,
            source_logical_id=source,
            target_logical_id=target,
            unresolved_descriptor="also-present",
        )


def test_route_normalization_preserves_semantic_trailing_slash() -> None:
    assert normalize_route_path("users//{id}") == "/users/{id}"
    assert normalize_route_path("/users/") == "/users/"


def test_records_are_immutable_and_reject_sensitive_metadata() -> None:
    entity = ArchitectureEntity(
        logical_id="architecture://entity/one",
        semantic_signature=semantic_signature({"identity": "one"}),
        kind=ArchitectureEntityKind.COMPONENT,
        name="One",
        namespace=("app",),
        status=ArchitectureFactStatus.CONFIRMED,
        evidence_ids=("ev-1",),
        source_ir_keys=("ir-1",),
        metadata={"framework": "fastapi"},
    )
    with pytest.raises(FrozenInstanceError):
        entity.name = "Other"  # type: ignore[misc]
    with pytest.raises(ArchitectureModelError, match="unsafe metadata"):
        ArchitectureEntity(
            logical_id="architecture://entity/two",
            semantic_signature=semantic_signature({"identity": "two"}),
            kind=ArchitectureEntityKind.COMPONENT,
            name="Two",
            namespace=("app",),
            status=ArchitectureFactStatus.CONFIRMED,
            evidence_ids=(),
            source_ir_keys=("ir-2",),
            metadata={"api_token": "not-allowed"},
        )


def test_architecture_evidence_rejects_host_paths_and_traversal() -> None:
    common = {
        "logical_id": "evidence://snapshot/id/key",
        "source_evidence_key": "key",
        "source_record_type": "syntax_fact",
    }
    with pytest.raises(ArchitectureModelError, match="host absolute path"):
        ArchitectureEvidence(path="/etc/passwd", **common)
    with pytest.raises(ArchitectureModelError, match="must not contain"):
        ArchitectureEvidence(path="src/../secret", **common)


def test_non_finite_metadata_is_rejected_from_canonical_records() -> None:
    with pytest.raises(ArchitectureModelError, match="non-finite"):
        ArchitectureEvidence(
            logical_id="evidence://snapshot/id/key",
            source_evidence_key="key",
            source_record_type="syntax_fact",
            path="src/app.py",
            metadata={"confidence": math.nan},
        )
