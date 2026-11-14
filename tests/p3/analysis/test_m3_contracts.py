"""Contract and foundation tests for Phase 3 Module 3 (Intermediate Representation).

Verifies draft F3 schema, immutability, enum semantics, key generation, metadata safety,
referential integrity, and canonical JSON serialization determinism.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from backend.platform.analysis.ir import (
    IR_SCHEMA_VERSION,
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
    IRValidationError,
    build_conflict_key,
    build_entity_key,
    build_evidence_key,
    build_relationship_key,
    build_unresolved_key,
    is_stronger,
)


def _make_minimal_document(
    entities: tuple[IREntity, ...] = (),
    relationships: tuple[IRRelationship, ...] = (),
    evidence: tuple[IREvidence, ...] = (),
    unresolved: tuple[IRUnresolvedReference, ...] = (),
    conflicts: tuple[IRConflict, ...] = (),
    is_partial: bool = False,
    repo_id: UUID | None = None,
    snap_id: UUID | None = None,
    analysis_id: UUID | None = None,
    project_id: UUID | None = None,
) -> IRDocument:
    """Helper creating a minimal valid IRDocument with default root entities."""
    r_id = repo_id or uuid4()
    s_id = snap_id or uuid4()
    a_id = analysis_id or uuid4()
    p_id = project_id or uuid4()
    repo_key = build_entity_key(IREntityKind.REPOSITORY, f"repo-{r_id}")
    snap_key = build_entity_key(IREntityKind.SNAPSHOT, f"snap-{s_id}")
    root_ev_key = build_evidence_key("inspection_root", "root", None)

    base_ev = IREvidence(
        evidence_key=root_ev_key,
        artifact_id=None,
        path="root",
        source_record_type="inspection_root",
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
        configuration_fingerprint="cfg-test",
        entities=all_ent,
        relationships=all_rel,
        evidence=all_ev,
        unresolved_references=unresolved,
        conflicts=conflicts,
        completeness=IRCompleteness(
            is_partial=is_partial,
            total_inventory_artifacts=len(all_ent),
            analyzed_artifacts=len(all_ent),
        ),
    )


class TestIRContractFoundation:
    """Tests for F3 schema constants, enums, and immutability."""

    def test_schema_version_is_1_0_0(self) -> None:
        assert IR_SCHEMA_VERSION == "1.0.0"

    def test_package_reexports_analyzer_and_schema_version(self) -> None:
        from backend.platform.analysis.ir import (
            ANALYZER_VERSION as PKG_ANALYZER_VERSION,
        )
        from backend.platform.analysis.ir import (
            IR_SCHEMA_VERSION as PKG_IR_SCHEMA_VERSION,
        )

        assert PKG_ANALYZER_VERSION is not None
        assert PKG_IR_SCHEMA_VERSION == "1.0.0"

    def test_entity_kinds_vocabulary(self) -> None:
        expected = {
            "repository",
            "snapshot",
            "artifact",
            "application",
            "module",
            "symbol",
            "component",
            "endpoint",
            "external_system",
            "database",
            "message_infrastructure",
            "configuration",
        }
        actual = {k.value for k in IREntityKind}
        assert actual == expected

    def test_relationship_kinds_vocabulary(self) -> None:
        expected = {
            "contains",
            "declares",
            "imports",
            "exports",
            "static_call_reference",
            "inherits",
            "composes",
            "declares_route",
            "uses_framework",
            "declares_dependency",
            "source_references_dependency",
        }
        actual = {k.value for k in IRRelationshipKind}
        assert actual == expected

    def test_fact_status_vocabulary(self) -> None:
        expected = {"confirmed", "inferred", "unresolved", "conflicting"}
        actual = {k.value for k in IRFactStatus}
        assert actual == expected

    def test_unresolved_reasons_vocabulary(self) -> None:
        expected = {
            "not_found",
            "ambiguous",
            "dynamic",
            "unsupported",
            "incomplete_input",
        }
        actual = {r.value for r in IRUnresolvedReason}
        assert actual == expected

    def test_evidence_strength_ranking(self) -> None:
        assert IREvidenceStrength.DIRECT_SOURCE.is_stronger(
            IREvidenceStrength.FRAMEWORK_STRUCTURAL
        )
        assert IREvidenceStrength.FRAMEWORK_STRUCTURAL.is_stronger(
            IREvidenceStrength.CONFIGURATION
        )
        assert IREvidenceStrength.CONFIGURATION.is_stronger(
            IREvidenceStrength.DEPENDENCY
        )
        assert IREvidenceStrength.DEPENDENCY.is_stronger(
            IREvidenceStrength.DOCUMENTATION
        )
        assert not IREvidenceStrength.DOCUMENTATION.is_stronger(
            IREvidenceStrength.DIRECT_SOURCE
        )
        assert is_stronger(
            IREvidenceStrength.DIRECT_SOURCE,
            IREvidenceStrength.DOCUMENTATION,
        )

    def test_all_reference_kinds_mapped(self) -> None:
        from backend.platform.analysis.ir.service import _REFERENCE_KIND_MAP
        from backend.platform.analysis.syntax.model import ReferenceKind

        relationship_kinds = set(ReferenceKind) - {
            ReferenceKind.NAME,
            ReferenceKind.ATTRIBUTE,
        }
        for rk in relationship_kinds:
            assert rk in _REFERENCE_KIND_MAP
            assert isinstance(_REFERENCE_KIND_MAP[rk], IRRelationshipKind)
        assert ReferenceKind.NAME not in _REFERENCE_KIND_MAP
        assert ReferenceKind.ATTRIBUTE not in _REFERENCE_KIND_MAP

    def test_records_are_frozen_immutable(self) -> None:
        ev = IREvidence(
            evidence_key="ev::1",
            artifact_id=None,
            path="src/a.py",
            source_record_type="test",
            strength=IREvidenceStrength.DIRECT_SOURCE,
        )
        with pytest.raises(FrozenInstanceError):
            ev.path = "src/b.py"  # type: ignore[misc]

        ent = IREntity(
            ir_key="entity::1",
            kind=IREntityKind.SYMBOL,
            name="foo",
            evidence_keys=("ev::1",),
        )
        with pytest.raises(FrozenInstanceError):
            ent.name = "bar"  # type: ignore[misc]

        doc = _make_minimal_document()
        with pytest.raises(FrozenInstanceError):
            doc.ir_schema_version = "2.0.0"  # type: ignore[misc]


class TestKeyGeneration:
    """Tests for deterministic key builders and normalization."""

    def test_entity_key_normalization(self) -> None:
        key = build_entity_key(
            IREntityKind.MODULE, "src\\nested\\module.py", "Class Item"
        )
        assert key == "module::src/nested/module.py::Class%20Item"

    def test_entity_key_encoding_is_collision_safe(self) -> None:
        spaced = build_entity_key(IREntityKind.ARTIFACT, "src/a b.py")
        underscored = build_entity_key(IREntityKind.ARTIFACT, "src/a_b.py")
        escaped = build_entity_key(IREntityKind.ARTIFACT, "src/a%20b.py")

        assert len({spaced, underscored, escaped}) == 3

    def test_entity_key_empty_raises_validation_error(self) -> None:
        with pytest.raises(IRValidationError, match="Cannot build entity key"):
            build_entity_key(IREntityKind.SYMBOL)

    def test_relationship_key_builder(self) -> None:
        key = build_relationship_key(
            IRRelationshipKind.IMPORTS,
            "module::src/a.py",
            "module::src/b.py",
            "sym::foo",
        )
        assert key == ("rel::imports::module::src/a.py::module::src/b.py::sym%3A%3Afoo")

    def test_relationship_key_with_none_target(self) -> None:
        key = build_relationship_key(
            IRRelationshipKind.DECLARES_DEPENDENCY,
            "artifact::package.json",
            None,
            "dep::react",
        )
        expected = (
            "rel::declares_dependency::artifact::package.json::unresolved::"
            "dep%3A%3Areact"
        )
        assert key == expected

    def test_evidence_key_builder(self) -> None:
        key = build_evidence_key("declaration_fact", "src/foo.py", "decl_123", "extra")
        assert key == "ev::src/foo.py::declaration_fact::decl_123::extra"

    def test_unresolved_key_builder(self) -> None:
        key = build_unresolved_key(
            "module::src/app.py",
            IRRelationshipKind.IMPORTS,
            "external_pkg",
            "fact_99",
        )
        assert key == "unres::module::src/app.py::imports::external_pkg::fact_99"

    def test_conflict_key_builder(self) -> None:
        key = build_conflict_key("entity_kind", "symbol::src/app.py::do_something")
        assert key == "conflict::entity_kind::symbol::src/app.py::do_something::none"


class TestMetadataSafety:
    """Tests preventing host file paths and secrets from leaking into IR metadata."""

    def test_reject_windows_host_path_in_entity_metadata(self) -> None:
        ev_key = build_evidence_key("test", "src/a.py", None)
        with pytest.raises(IRValidationError, match="host absolute path"):
            IREntity(
                ir_key="symbol::src/a.py::f",
                kind=IREntityKind.SYMBOL,
                name="f",
                evidence_keys=(ev_key,),
                metadata={"host_location": "C:\\Users\\shrey\\project\\a.py"},
            )

    def test_reject_unix_host_path_in_evidence_metadata(self) -> None:
        with pytest.raises(IRValidationError, match="host absolute path"):
            IREvidence(
                evidence_key="ev::1",
                artifact_id=None,
                path="src/a.py",
                source_record_type="test",
                strength=IREvidenceStrength.CONFIGURATION,
                metadata={"file": "/home/user/project/a.py"},
            )

    def test_reject_unc_host_path_in_metadata(self) -> None:
        ev_key = build_evidence_key("test", "src/a.py", None)
        with pytest.raises(IRValidationError, match="host absolute path"):
            IREntity(
                ir_key="symbol::src/a.py::f",
                kind=IREntityKind.SYMBOL,
                name="f",
                evidence_keys=(ev_key,),
                metadata={"network_share": "\\\\server\\share\\repo\\file.py"},
            )

        with pytest.raises(IRValidationError, match="host absolute path"):
            IREntity(
                ir_key="symbol::src/a.py::f2",
                kind=IREntityKind.SYMBOL,
                name="f2",
                evidence_keys=(ev_key,),
                metadata={"extended_path": "\\\\?\\C:\\repo\\file.py"},
            )

    def test_reject_unc_path_in_string_fields(self) -> None:
        with pytest.raises(IRValidationError, match="host absolute path"):
            IREvidence(
                evidence_key="ev::1",
                artifact_id=None,
                path="\\\\server\\share\\a.py",
                source_record_type="test",
                strength=IREvidenceStrength.CONFIGURATION,
            )

    def test_reject_bare_auth_key_in_metadata(self) -> None:
        ev_key = build_evidence_key("test", "src/a.py", None)
        with pytest.raises(IRValidationError, match="sensitive term"):
            IREntity(
                ir_key="symbol::src/a.py::auth_cfg",
                kind=IREntityKind.SYMBOL,
                name="auth_cfg",
                evidence_keys=(ev_key,),
                metadata={"auth": "secret_bearer_value"},
            )

    def test_reject_sensitive_token_keys_in_metadata(self) -> None:
        ev_key = build_evidence_key("test", "src/a.py", None)
        with pytest.raises(IRValidationError, match="sensitive term"):
            IREntity(
                ir_key="symbol::src/a.py::login",
                kind=IREntityKind.SYMBOL,
                name="login",
                evidence_keys=(ev_key,),
                metadata={"auth_token": "secret123"},
            )

        with pytest.raises(IRValidationError, match="sensitive term"):
            IREntity(
                ir_key="symbol::src/a.py::cfg",
                kind=IREntityKind.SYMBOL,
                name="cfg",
                evidence_keys=(ev_key,),
                metadata={"db_password": "mypassword"},
            )

    def test_allow_safe_nested_metadata(self) -> None:
        ev_key = build_evidence_key("test", "src/a.py", None)
        ent = IREntity(
            ir_key="symbol::src/a.py::f",
            kind=IREntityKind.SYMBOL,
            name="f",
            evidence_keys=(ev_key,),
            metadata={
                "signals": ["import", "call"],
                "options": {"strict": True, "limit": 100},
            },
        )
        assert ent.metadata["signals"] == ("import", "call")
        assert ent.metadata["options"]["limit"] == 100
        assert ent.metadata["options"]["strict"] is True


class TestReferentialIntegrity:
    """Tests that IRDocument enforces integrity across keys."""

    def test_reject_duplicate_entity_keys(self) -> None:
        repo_id = uuid4()
        snap_id = uuid4()
        root_ev = IREvidence(
            evidence_key="ev::root",
            artifact_id=None,
            path="root",
            source_record_type="root",
            strength=IREvidenceStrength.CONFIGURATION,
        )
        ent1 = IREntity(
            ir_key="symbol::src/a.py::foo",
            kind=IREntityKind.SYMBOL,
            name="foo",
            evidence_keys=("ev::root",),
        )
        ent2 = IREntity(
            ir_key="symbol::src/a.py::foo",
            kind=IREntityKind.SYMBOL,
            name="foo_dup",
            evidence_keys=("ev::root",),
        )
        with pytest.raises(IRValidationError, match="Duplicate entity"):
            IRDocument(
                analysis_id=uuid4(),
                project_id=uuid4(),
                repository_id=repo_id,
                snapshot_id=snap_id,
                configuration_fingerprint="cfg-test",
                entities=(ent1, ent2),
                relationships=(),
                evidence=(root_ev,),
                unresolved_references=(),
                conflicts=(),
                completeness=IRCompleteness(is_partial=True),
            )

    def test_reject_relationship_with_unknown_source_key(self) -> None:
        root_ev = IREvidence(
            evidence_key="ev::root",
            artifact_id=None,
            path="root",
            source_record_type="root",
            strength=IREvidenceStrength.CONFIGURATION,
        )
        ent = IREntity(
            ir_key="symbol::src/a.py::foo",
            kind=IREntityKind.SYMBOL,
            name="foo",
            evidence_keys=("ev::root",),
        )
        rel = IRRelationship(
            ir_key="rel::contains::missing->symbol::src/a.py::foo",
            kind=IRRelationshipKind.CONTAINS,
            source_key="missing",
            target_key="symbol::src/a.py::foo",
            evidence_keys=("ev::root",),
        )
        with pytest.raises(IRValidationError, match="unknown source_key"):
            IRDocument(
                analysis_id=uuid4(),
                project_id=uuid4(),
                repository_id=uuid4(),
                snapshot_id=uuid4(),
                configuration_fingerprint="cfg-test",
                entities=(ent,),
                relationships=(rel,),
                evidence=(root_ev,),
                unresolved_references=(),
                conflicts=(),
                completeness=IRCompleteness(is_partial=True),
            )

    def test_reject_dangling_evidence_key(self) -> None:
        ent = IREntity(
            ir_key="symbol::src/a.py::foo",
            kind=IREntityKind.SYMBOL,
            name="foo",
            evidence_keys=("ev::nonexistent",),
        )
        with pytest.raises(IRValidationError, match="unknown evidence_key"):
            IRDocument(
                analysis_id=uuid4(),
                project_id=uuid4(),
                repository_id=uuid4(),
                snapshot_id=uuid4(),
                configuration_fingerprint="cfg-test",
                entities=(ent,),
                relationships=(),
                evidence=(),
                unresolved_references=(),
                conflicts=(),
                completeness=IRCompleteness(is_partial=True),
            )


class TestCanonicalSerialization:
    """Tests determinism of to_canonical_json() under shuffled inputs."""

    def test_canonical_json_byte_equivalence_on_shuffled_inputs(self) -> None:
        ev1 = IREvidence(
            evidence_key="ev::1",
            artifact_id=None,
            path="src/a.py",
            source_record_type="decl",
            strength=IREvidenceStrength.DIRECT_SOURCE,
        )
        ev2 = IREvidence(
            evidence_key="ev::2",
            artifact_id=None,
            path="src/b.py",
            source_record_type="decl",
            strength=IREvidenceStrength.DIRECT_SOURCE,
        )
        ent1 = IREntity(
            ir_key="symbol::src/a.py::Alpha",
            kind=IREntityKind.SYMBOL,
            name="Alpha",
            evidence_keys=("ev::1",),
        )
        ent2 = IREntity(
            ir_key="symbol::src/b.py::Beta",
            kind=IREntityKind.SYMBOL,
            name="Beta",
            evidence_keys=("ev::2",),
        )
        rel1 = IRRelationship(
            ir_key=build_relationship_key(
                IRRelationshipKind.CONTAINS,
                "symbol::src/a.py::Alpha",
                "symbol::src/b.py::Beta",
            ),
            kind=IRRelationshipKind.CONTAINS,
            source_key="symbol::src/a.py::Alpha",
            target_key="symbol::src/b.py::Beta",
            evidence_keys=("ev::1",),
        )

        fixed_repo_id = uuid4()
        fixed_snap_id = uuid4()
        fixed_analysis_id = uuid4()
        fixed_project_id = uuid4()

        doc_forward = _make_minimal_document(
            entities=(ent1, ent2),
            relationships=(rel1,),
            evidence=(ev1, ev2),
            repo_id=fixed_repo_id,
            snap_id=fixed_snap_id,
            analysis_id=fixed_analysis_id,
            project_id=fixed_project_id,
        )
        doc_reversed = _make_minimal_document(
            entities=(ent2, ent1),
            relationships=(rel1,),
            evidence=(ev2, ev1),
            repo_id=fixed_repo_id,
            snap_id=fixed_snap_id,
            analysis_id=fixed_analysis_id,
            project_id=fixed_project_id,
        )

        json_forward = doc_forward.to_canonical_json()
        json_reversed = doc_reversed.to_canonical_json()

        assert json_forward == json_reversed
        assert json_forward.encode("utf-8") == json_reversed.encode("utf-8")

    def test_streamed_canonical_json_is_byte_identical_to_legacy_encoding(self) -> None:
        """The bounded serializer must preserve the frozen canonical F3 bytes."""
        document = _make_minimal_document()
        expected = json.dumps(
            document.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        actual = document.to_canonical_json().encode("utf-8")

        assert actual == expected
        assert document.canonical_json_size_bytes() == len(expected)
