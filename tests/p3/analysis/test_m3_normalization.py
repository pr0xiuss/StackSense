"""Normalization tests for Phase 3 Module 3 (Intermediate Representation).

Verifies deterministic transformation of frozen F2 RepositoryInspectionResult
into draft F3 IRDocument across inventory, language/runtime/framework detections,
syntax documents, facts (declaration, import, export, reference, framework, manifest),
completeness computation, and conflict detection.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.platform.analysis.inspection.model import (
    ArtifactAnalysisRole,
    ArtifactProcessingOutcome,
    FrameworkDetection,
    LanguageDetection,
    RuntimeDetection,
)
from backend.platform.analysis.ir import (
    IRConstructionError,
    IRConstructionService,
    IREntityKind,
    IREvidenceStrength,
    IRFactStatus,
    IRRelationshipKind,
    IRUnresolvedReason,
)
from backend.platform.analysis.syntax.model import (
    DeclarationKind,
    ExportKind,
    ImportKind,
    ReferenceKind,
)
from backend.platform.ingestion.domain.constants import (
    ArtifactCategory,
    SupportLevel,
)
from tests.p3.analysis.m3_test_helper import (
    create_mock_declaration_fact,
    create_mock_export_fact,
    create_mock_import_fact,
    create_mock_inspection_result,
    create_mock_inventory_entry,
    create_mock_manifest_fact,
    create_mock_reference_fact,
    create_mock_source_range,
    create_mock_syntax_document,
)


class TestF2ConsumerBoundary:
    """Tests consumer contract enforcement on incoming F2 results."""

    def test_reject_non_inspection_result(self) -> None:
        service = IRConstructionService()
        with pytest.raises(
            IRConstructionError, match="Expected RepositoryInspectionResult"
        ):
            service.construct("invalid-input")  # type: ignore[arg-type]

    def test_reject_unsupported_f2_version(self) -> None:
        service = IRConstructionService()
        inspection = create_mock_inspection_result()
        # Create an object with f2_version != "1.0.0" bypassing post_init
        object.__setattr__(inspection, "f2_version", "2.0.0")
        with pytest.raises(
            IRConstructionError, match="Unsupported F2 contract version"
        ):
            service.construct(inspection)

    def test_reject_unexpected_schema_version(self) -> None:
        service = IRConstructionService()
        inspection = create_mock_inspection_result()
        with pytest.raises(
            IRConstructionError, match="Unsupported expected IR schema version"
        ):
            service.construct(inspection, expected_schema_version="2.0.0")


class TestInventoryNormalization:
    """Tests mapping of F2 inventory to IR artifacts and relationships."""

    def test_inventory_creates_artifact_entities_and_contains_rel(self) -> None:
        service = IRConstructionService()
        art_id = uuid4()
        entry = create_mock_inventory_entry(
            path="src/service.py",
            artifact_id=art_id,
            detected_language="python",
            role=ArtifactAnalysisRole.SEMANTIC,
            outcome=ArtifactProcessingOutcome.ANALYZED,
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
            size_bytes=1024,
            content_hash="h" * 64,
        )
        inspection = create_mock_inspection_result(inventory=[entry])

        doc = service.construct(inspection)

        # Artifact entity
        art_keys = [e.ir_key for e in doc.entities if e.kind == IREntityKind.ARTIFACT]
        assert "artifact::src/service.py" in art_keys
        art_entity = next(
            e for e in doc.entities if e.ir_key == "artifact::src/service.py"
        )
        assert art_entity.artifact_id == art_id
        assert art_entity.language == "python"
        assert art_entity.metadata["size_bytes"] == 1024

        # Contains relationship: snapshot -> artifact
        snap_key = f"snapshot::{inspection.snapshot_id}"
        contains_rels = [
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.CONTAINS
            and r.source_key == snap_key
            and r.target_key == "artifact::src/service.py"
        ]
        assert len(contains_rels) == 1
        assert contains_rels[0].status == IRFactStatus.CONFIRMED

        # Inventory evidence
        inv_ev = next(
            ev
            for ev in doc.evidence
            if ev.source_record_type == "inventory_entry"
            and ev.path == "src/service.py"
        )
        assert inv_ev.artifact_id == art_id
        assert inv_ev.strength == IREvidenceStrength.CONFIGURATION
        assert inv_ev.metadata["category"] == "source_code"
        assert inv_ev.metadata["support_level"] == "full"


class TestLanguageAndEnvironmentNormalization:
    """Tests normalization of language, runtime, and framework detections."""

    def test_language_detection_enriches_artifact_and_adds_evidence(
        self,
    ) -> None:
        service = IRConstructionService()
        entry = create_mock_inventory_entry(path="app.js")
        ld = LanguageDetection(
            artifact_id=entry.artifact_id,
            path="app.js",
            language="javascript",
            confidence="confirmed",
            evidence_signals=("extension", "shebang"),
        )
        inspection = create_mock_inspection_result(
            inventory=[entry],
            language_detections=[ld],
        )

        doc = service.construct(inspection)

        art_ent = next(e for e in doc.entities if e.ir_key == "artifact::app.js")
        assert art_ent.language == "javascript"
        ld_ev = next(
            ev for ev in doc.evidence if ev.source_record_type == "language_detection"
        )
        assert ld_ev.metadata["language"] == "javascript"
        assert ld_ev.metadata["confidence"] == "confirmed"
        assert ld_ev.evidence_key in art_ent.evidence_keys

    def test_runtime_and_framework_detections_create_evidence(self) -> None:
        service = IRConstructionService()
        rd = RuntimeDetection(
            runtime="node",
            target="v18",
            evidence_signals=("package.json:engines",),
        )
        fd = FrameworkDetection(
            framework="express",
            status="detected",
            version="^4.18.0",
            evidence_signals=("package.json:dependencies",),
        )
        inspection = create_mock_inspection_result(
            runtime_detections=[rd],
            framework_detections=[fd],
        )

        doc = service.construct(inspection)

        rd_ev = next(
            ev for ev in doc.evidence if ev.source_record_type == "runtime_detection"
        )
        assert rd_ev.metadata["runtime"] == "node"

        fd_ev = next(
            ev for ev in doc.evidence if ev.source_record_type == "framework_detection"
        )
        assert fd_ev.metadata["framework"] == "express"
        assert fd_ev.metadata["version"] == "^4.18.0"


class TestSyntaxAndFactNormalization:
    """Tests syntax documents and individual fact normalizations."""

    def test_syntax_document_and_declarations(self) -> None:
        service = IRConstructionService()
        range_fn = create_mock_source_range(0, 50, 1, 3, 0, 1)
        decl_fn = create_mock_declaration_fact(
            fact_key="decl::fn::1",
            name="calculate_tax",
            kind=DeclarationKind.FUNCTION,
            declaration_range=range_fn,
            name_range=create_mock_source_range(4, 17, 1, 1, 4, 17),
        )

        range_comp = create_mock_source_range(60, 150, 5, 10, 0, 1)
        decl_comp = create_mock_declaration_fact(
            fact_key="decl::comp::2",
            name="UserProfile",
            kind=DeclarationKind.REACT_COMPONENT,
            declaration_range=range_comp,
            name_range=create_mock_source_range(66, 77, 5, 5, 6, 17),
        )

        syntax_doc = create_mock_syntax_document(
            path="src/components.tsx",
            language="typescript",
            declarations=[decl_fn, decl_comp],
        )
        entry = create_mock_inventory_entry(path="src/components.tsx")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        # Module entity
        mod_key = "module::src/components.tsx"
        assert any(e.ir_key == mod_key for e in doc.entities)

        # Function symbol entity
        fn_key = "symbol::src/components.tsx::calculate_tax::0_50"
        fn_ent = next((e for e in doc.entities if e.ir_key == fn_key), None)
        assert fn_ent is not None
        assert fn_ent.kind == IREntityKind.SYMBOL
        assert fn_ent.module_key == mod_key

        # Component entity
        comp_key = "component::src/components.tsx::UserProfile::60_150"
        comp_ent = next((e for e in doc.entities if e.ir_key == comp_key), None)
        assert comp_ent is not None
        assert comp_ent.kind == IREntityKind.COMPONENT
        assert comp_ent.module_key == mod_key

        # Declares relationships: module -> symbol / component
        rel_fn = next(
            r
            for r in doc.relationships
            if r.source_key == mod_key and r.target_key == fn_key
        )
        assert rel_fn.kind == IRRelationshipKind.DECLARES

        # Fact evidence preserves parser adapter metadata
        fn_ev = next(ev for ev in doc.evidence if ev.source_fact_key == "decl::fn::1")
        assert fn_ev.parser_adapter_id == "mock-tree-sitter"
        assert fn_ev.grammar_abi_version == 14
        assert fn_ev.source_range == range_fn

    def test_import_fact_creates_unresolved_reference(self) -> None:
        service = IRConstructionService()
        imp_fact = create_mock_import_fact(
            fact_key="imp::1",
            source_module="os.path",
            imported_name="join",
            local_alias="pjoin",
            kind=ImportKind.NAMED,
            range=create_mock_source_range(0, 25),
        )
        syntax_doc = create_mock_syntax_document(
            path="src/utils.py",
            imports=[imp_fact],
        )
        entry = create_mock_inventory_entry(path="src/utils.py")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        # Relationship is IMPORTS with target_key=None
        imp_rels = [
            r for r in doc.relationships if r.kind == IRRelationshipKind.IMPORTS
        ]
        assert len(imp_rels) == 1
        assert imp_rels[0].target_key is None
        assert imp_rels[0].unresolved_reference_key is not None

        # Unresolved reference is recorded
        unres = next(
            u
            for u in doc.unresolved_references
            if u.relationship_kind == IRRelationshipKind.IMPORTS
        )
        assert unres.target_name == "os.path"
        assert unres.reason == IRUnresolvedReason.NOT_FOUND

    def test_export_fact_local_resolves_and_external_unresolved(self) -> None:
        service = IRConstructionService()
        range_fn = create_mock_source_range(0, 40)
        decl_fn = create_mock_declaration_fact(
            fact_key="decl::fn::1",
            name="helper",
            kind=DeclarationKind.FUNCTION,
            declaration_range=range_fn,
            name_range=create_mock_source_range(4, 10),
        )
        exp_local = create_mock_export_fact(
            fact_key="exp::1",
            exported_name="helper",
            local_name="helper",
            kind=ExportKind.NAMED,
            range=create_mock_source_range(50, 70),
        )
        exp_external = create_mock_export_fact(
            fact_key="exp::2",
            exported_name="externalThing",
            local_name="externalThing",
            kind=ExportKind.NAMED,
            range=create_mock_source_range(80, 110),
        )
        syntax_doc = create_mock_syntax_document(
            path="src/index.js",
            language="javascript",
            declarations=[decl_fn],
            exports=[exp_local, exp_external],
        )
        entry = create_mock_inventory_entry(path="src/index.js")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        # Local export resolves to local symbol
        sym_key = "symbol::src/index.js::helper::0_40"
        rel_local = next(
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.EXPORTS
            and r.metadata.get("exported_name") == "helper"
        )
        assert rel_local.target_key == sym_key
        assert rel_local.unresolved_reference_key is None

        # External export is unresolved
        rel_ext = next(
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.EXPORTS
            and r.metadata.get("exported_name") == "externalThing"
        )
        assert rel_ext.target_key is None
        assert rel_ext.unresolved_reference_key is not None

    def test_reference_fact_relationships(self) -> None:
        service = IRConstructionService()
        range_target = create_mock_source_range(0, 30)
        decl_target = create_mock_declaration_fact(
            fact_key="decl::fn::log",
            name="log_event",
            kind=DeclarationKind.FUNCTION,
            declaration_range=range_target,
            name_range=create_mock_source_range(4, 13),
        )
        call_ref = create_mock_reference_fact(
            fact_key="ref::call::1",
            target_name="log_event",
            kind=ReferenceKind.CALL,
            range=create_mock_source_range(40, 55),
        )
        inherit_ref = create_mock_reference_fact(
            fact_key="ref::inherit::2",
            target_name="BaseService",
            kind=ReferenceKind.INHERITANCE,
            range=create_mock_source_range(60, 80),
        )
        syntax_doc = create_mock_syntax_document(
            path="src/app.py",
            declarations=[decl_target],
            references=[call_ref, inherit_ref],
        )
        entry = create_mock_inventory_entry(path="src/app.py")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        # Call reference to local symbol
        call_rel = next(
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.STATIC_CALL_REFERENCE
        )
        target_sym = "symbol::src/app.py::log_event::0_30"
        assert call_rel.target_key == target_sym

        # Inheritance reference to external class
        inherit_rel = next(
            r for r in doc.relationships if r.kind == IRRelationshipKind.INHERITS
        )
        assert inherit_rel.target_key is None
        assert inherit_rel.unresolved_reference_key is not None

    def test_name_and_attribute_reference_fact_mapping(self) -> None:
        service = IRConstructionService()
        ref_name = create_mock_reference_fact(
            fact_key="ref::name::1",
            target_name="ConfigHolder",
            kind=ReferenceKind.NAME,
            range=create_mock_source_range(0, 12),
        )
        ref_attr = create_mock_reference_fact(
            fact_key="ref::attr::1",
            target_name="host_name",
            kind=ReferenceKind.ATTRIBUTE,
            range=create_mock_source_range(20, 29),
        )
        syntax_doc = create_mock_syntax_document(
            path="src/config.py",
            references=[ref_name, ref_attr],
        )
        entry = create_mock_inventory_entry(path="src/config.py")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        rels = [
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.STATIC_CALL_REFERENCE
        ]
        assert len(rels) == 2
        ref_kinds = {r.metadata.get("reference_kind") for r in rels}
        assert "name" in ref_kinds
        assert "attribute" in ref_kinds

    def test_manifest_fact_creates_declares_dependency(self) -> None:
        service = IRConstructionService()
        manifest = create_mock_manifest_fact(
            fact_key="man::1",
            manifest_type="package.json",
            name="react",
            version="^18.2.0",
            range=create_mock_source_range(0, 20),
            is_dev=False,
        )
        syntax_doc = create_mock_syntax_document(
            path="package.json",
            language="json",
            manifest_facts=[manifest],
        )
        entry = create_mock_inventory_entry(
            path="package.json",
            category=ArtifactCategory.DEPENDENCY_METADATA,
        )
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        dep_rel = next(
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.DECLARES_DEPENDENCY
        )
        assert dep_rel.source_key == "artifact::package.json"
        assert dep_rel.target_key is None
        assert dep_rel.unresolved_reference_key is None
        assert dep_rel.metadata["dependency_name"] == "react"
        assert dep_rel.metadata["version"] == "^18.2.0"
        assert len(doc.unresolved_references) == 0

    def test_ambiguous_local_declaration_resolution(self) -> None:
        service = IRConstructionService()
        d1 = create_mock_declaration_fact(
            fact_key="decl::fn::1",
            name="duplicate_fn",
            kind=DeclarationKind.FUNCTION,
            declaration_range=create_mock_source_range(0, 30),
            name_range=create_mock_source_range(4, 16),
        )
        d2 = create_mock_declaration_fact(
            fact_key="decl::fn::2",
            name="duplicate_fn",
            kind=DeclarationKind.FUNCTION,
            declaration_range=create_mock_source_range(40, 70),
            name_range=create_mock_source_range(44, 56),
        )
        ref = create_mock_reference_fact(
            fact_key="ref::call::1",
            target_name="duplicate_fn",
            kind=ReferenceKind.CALL,
            range=create_mock_source_range(80, 100),
        )
        syntax_doc = create_mock_syntax_document(
            path="src/ambig.py",
            declarations=[d1, d2],
            references=[ref],
        )
        entry = create_mock_inventory_entry(path="src/ambig.py")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        # Unresolved with reason AMBIGUOUS because 2 declarations have the same name
        unres = next(
            u for u in doc.unresolved_references if u.target_name == "duplicate_fn"
        )
        assert unres.reason == IRUnresolvedReason.AMBIGUOUS
        assert len(unres.candidate_references) == 2


class TestPartialCompletenessHandling:
    """Tests completeness calculation and partial execution flags."""

    def test_failed_outcome_marks_is_partial_true(self) -> None:
        service = IRConstructionService()
        e_ok = create_mock_inventory_entry(
            path="src/a.py", outcome=ArtifactProcessingOutcome.ANALYZED
        )
        e_fail = create_mock_inventory_entry(
            path="src/b.py", outcome=ArtifactProcessingOutcome.FAILED
        )
        inspection = create_mock_inspection_result(inventory=[e_ok, e_fail])

        doc = service.construct(inspection)

        assert doc.completeness.is_partial is True
        assert doc.completeness.total_inventory_artifacts == 2
        assert doc.completeness.failed_artifacts == 1

    def test_syntax_failed_parse_status_marks_is_partial_true(self) -> None:
        from backend.platform.analysis.syntax.model import ParseStatus

        service = IRConstructionService()
        e1 = create_mock_inventory_entry(
            path="src/broken.py", outcome=ArtifactProcessingOutcome.ANALYZED
        )
        syntax_doc = create_mock_syntax_document(
            path="src/broken.py",
            parse_status=ParseStatus.FAILED,
        )
        inspection = create_mock_inspection_result(
            inventory=[e1],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        assert doc.completeness.is_partial is True

    def test_clean_outcome_marks_is_partial_false(self) -> None:
        service = IRConstructionService()
        e1 = create_mock_inventory_entry(
            path="src/a.py", outcome=ArtifactProcessingOutcome.ANALYZED
        )
        e2 = create_mock_inventory_entry(
            path="src/b.py", outcome=ArtifactProcessingOutcome.ANALYZED
        )
        inspection = create_mock_inspection_result(inventory=[e1, e2])

        doc = service.construct(inspection)

        assert doc.completeness.is_partial is False
        assert doc.completeness.total_inventory_artifacts == 2
        assert doc.completeness.failed_artifacts == 0


_FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "p3" / "m3"


class TestFixtureDrivenNormalization:
    """Tests normalization using realistic on-disk fixtures."""

    def test_partial_sample_fixture_causes_partial_completeness(self) -> None:
        from backend.platform.analysis.syntax.model import ParseStatus

        fixture_path = _FIXTURES_DIR / "partial_sample.py"
        assert fixture_path.exists()
        content = fixture_path.read_text(encoding="utf-8")
        assert "broken_syntax" in content

        service = IRConstructionService()
        entry = create_mock_inventory_entry(
            path="tests/fixtures/p3/m3/partial_sample.py"
        )
        syntax_doc = create_mock_syntax_document(
            path="tests/fixtures/p3/m3/partial_sample.py",
            parse_status=ParseStatus.FAILED,
        )
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )
        doc = service.construct(inspection)
        assert doc.completeness.is_partial is True

    def test_conflict_sample_fixture_causes_ambiguous_resolution(self) -> None:
        fixture_path = _FIXTURES_DIR / "conflict_sample.py"
        assert fixture_path.exists()
        content = fixture_path.read_text(encoding="utf-8")
        assert "execute_task" in content

        service = IRConstructionService()
        d1 = create_mock_declaration_fact(
            fact_key="decl::fn::1",
            name="execute_task",
            kind=DeclarationKind.FUNCTION,
        )
        d2 = create_mock_declaration_fact(
            fact_key="decl::fn::2",
            name="execute_task",
            kind=DeclarationKind.FUNCTION,
        )
        ref = create_mock_reference_fact(
            fact_key="ref::call::1",
            target_name="execute_task",
            kind=ReferenceKind.CALL,
        )
        entry = create_mock_inventory_entry(
            path="tests/fixtures/p3/m3/conflict_sample.py"
        )
        syntax_doc = create_mock_syntax_document(
            path="tests/fixtures/p3/m3/conflict_sample.py",
            declarations=[d1, d2],
            references=[ref],
        )
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )
        doc = service.construct(inspection)
        unres = next(
            u for u in doc.unresolved_references if u.target_name == "execute_task"
        )
        assert unres.reason == IRUnresolvedReason.AMBIGUOUS

    def test_cap_fixture_json_creates_manifest_dependencies(self) -> None:
        fixture_path = _FIXTURES_DIR / "cap_fixture.json"
        assert fixture_path.exists()
        raw_manifest = json.loads(fixture_path.read_text(encoding="utf-8"))
        all_deps = {
            **raw_manifest.get("dependencies", {}),
            **raw_manifest.get("devDependencies", {}),
        }

        manifest_facts = [
            create_mock_manifest_fact(
                fact_key=f"man::{pkg}",
                name=pkg,
                version=ver,
                manifest_type="package.json",
            )
            for pkg, ver in all_deps.items()
        ]

        service = IRConstructionService()
        entry = create_mock_inventory_entry(path="cap_fixture.json")
        syntax_doc = create_mock_syntax_document(
            path="cap_fixture.json",
            language="json",
            manifest_facts=manifest_facts,
        )
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )
        doc = service.construct(inspection)
        dep_rels = [
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.DECLARES_DEPENDENCY
        ]
        assert len(dep_rels) == len(all_deps)
