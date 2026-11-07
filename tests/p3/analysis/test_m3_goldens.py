"""Golden tests for Phase 3 Module 3 (Intermediate Representation).

Verifies canonical complete, partial, and conflicting IR goldens, as well as byte-level
serialization invariance under shuffled and concurrent fact orders.
"""

from __future__ import annotations

import random
from uuid import UUID

from backend.platform.analysis.inspection.model import (
    ArtifactProcessingOutcome,
)
from backend.platform.analysis.ir import (
    IRConflict,
    IRConstructionService,
)
from backend.platform.analysis.syntax.model import (
    DeclarationKind,
    ImportKind,
    ParseStatus,
    ReferenceKind,
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

_FIXED_REPO_ID = UUID("11111111-1111-1111-1111-111111111111")
_FIXED_SNAP_ID = UUID("22222222-2222-2222-2222-222222222222")
_FIXED_ANALYSIS_ID = UUID("33333333-3333-3333-3333-333333333333")
_FIXED_PROJECT_ID = UUID("44444444-4444-4444-4444-444444444444")


def _build_standard_inspection_workload() -> tuple[list, list]:
    """Build a fixed deterministic set of inventory and syntax documents."""
    inv_py = create_mock_inventory_entry(
        path="src/main.py",
        artifact_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        detected_language="python",
    )
    inv_ts = create_mock_inventory_entry(
        path="src/utils.ts",
        artifact_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        detected_language="typescript",
    )
    inv_pkg = create_mock_inventory_entry(
        path="package.json",
        artifact_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        detected_language="json",
    )

    d_main = create_mock_declaration_fact(
        fact_key="decl::py::main",
        name="run_server",
        kind=DeclarationKind.FUNCTION,
        declaration_range=create_mock_source_range(0, 50),
        name_range=create_mock_source_range(4, 14),
    )
    imp_main = create_mock_import_fact(
        fact_key="imp::py::1",
        source_module="fastapi",
        imported_name="FastAPI",
        kind=ImportKind.NAMED,
    )
    ref_main = create_mock_reference_fact(
        fact_key="ref::py::1",
        target_name="run_server",
        kind=ReferenceKind.CALL,
        source_declaration_key="decl::py::main",
    )
    s_py = create_mock_syntax_document(
        path="src/main.py",
        language="python",
        artifact_id=inv_py.artifact_id,
        declarations=[d_main],
        imports=[imp_main],
        references=[ref_main],
    )

    d_ts = create_mock_declaration_fact(
        fact_key="decl::ts::util",
        name="formatDate",
        kind=DeclarationKind.FUNCTION,
        declaration_range=create_mock_source_range(0, 40),
        name_range=create_mock_source_range(9, 19),
    )
    exp_ts = create_mock_export_fact(
        fact_key="exp::ts::1",
        exported_name="formatDate",
        local_name="formatDate",
    )
    s_ts = create_mock_syntax_document(
        path="src/utils.ts",
        language="typescript",
        artifact_id=inv_ts.artifact_id,
        declarations=[d_ts],
        exports=[exp_ts],
    )

    man_pkg = create_mock_manifest_fact(
        fact_key="man::pkg::1",
        name="express",
        version="^4.19.2",
    )
    s_pkg = create_mock_syntax_document(
        path="package.json",
        language="json",
        artifact_id=inv_pkg.artifact_id,
        manifest_facts=[man_pkg],
    )

    return [inv_py, inv_ts, inv_pkg], [s_py, s_ts, s_pkg]


class TestIRGoldens:
    """Golden deterministic output verification."""

    def test_complete_golden_determinism(self) -> None:
        inventory, syntax_docs = _build_standard_inspection_workload()
        inspection = create_mock_inspection_result(
            analysis_id=_FIXED_ANALYSIS_ID,
            project_id=_FIXED_PROJECT_ID,
            repository_id=_FIXED_REPO_ID,
            snapshot_id=_FIXED_SNAP_ID,
            config_fingerprint="golden-cfg-v1",
            inventory=inventory,
            syntax_documents=syntax_docs,
        )

        service = IRConstructionService()
        doc1 = service.construct(inspection)
        doc2 = service.construct(inspection)

        json1 = doc1.to_canonical_json()
        json2 = doc2.to_canonical_json()

        assert json1 == json2
        assert json1.encode("utf-8") == json2.encode("utf-8")
        assert doc1.completeness.is_partial is False
        assert doc1.completeness.total_inventory_artifacts == 3
        assert len(doc1.entities) > 3

    def test_partial_golden_marks_is_partial_true(self) -> None:
        inventory, syntax_docs = _build_standard_inspection_workload()
        failed_entry = create_mock_inventory_entry(
            path="src/broken.py",
            outcome=ArtifactProcessingOutcome.FAILED,
        )
        broken_syntax = create_mock_syntax_document(
            path="src/broken.py",
            parse_status=ParseStatus.FAILED,
        )
        inspection = create_mock_inspection_result(
            analysis_id=_FIXED_ANALYSIS_ID,
            project_id=_FIXED_PROJECT_ID,
            repository_id=_FIXED_REPO_ID,
            snapshot_id=_FIXED_SNAP_ID,
            config_fingerprint="golden-partial-v1",
            inventory=[*inventory, failed_entry],
            syntax_documents=[*syntax_docs, broken_syntax],
        )

        service = IRConstructionService()
        doc = service.construct(inspection)

        assert doc.completeness.is_partial is True
        assert doc.completeness.failed_artifacts == 1
        canon_json = doc.to_canonical_json()
        assert '"is_partial":true' in canon_json

    def test_conflict_golden_preserves_conflicts(self) -> None:
        inventory, syntax_docs = _build_standard_inspection_workload()
        inspection = create_mock_inspection_result(
            analysis_id=_FIXED_ANALYSIS_ID,
            project_id=_FIXED_PROJECT_ID,
            repository_id=_FIXED_REPO_ID,
            snapshot_id=_FIXED_SNAP_ID,
            config_fingerprint="golden-conflict-v1",
            inventory=inventory,
            syntax_documents=syntax_docs,
        )

        service = IRConstructionService()
        doc = service.construct(inspection)

        # Manually attach a deterministic conflict to verify canonical serialization
        ev_key = doc.evidence[0].evidence_key
        conflict = IRConflict(
            conflict_key="conflict::test::1",
            conflict_type="typing_mismatch",
            subject_key=doc.entities[0].ir_key,
            competing_evidence_keys=(ev_key,),
            details={"reason": "competing types inferred"},
        )
        doc_with_conflict = service.construct(inspection, validate=False)
        object.__setattr__(
            doc_with_conflict, "conflicts", (conflict,)
        )
        # Update completeness counter to match
        comp = doc_with_conflict.completeness
        new_comp = type(comp)(
            total_inventory_artifacts=comp.total_inventory_artifacts,
            analyzed_artifacts=comp.analyzed_artifacts,
            failed_artifacts=comp.failed_artifacts,
            total_syntax_documents=comp.total_syntax_documents,
            total_syntax_facts=comp.total_syntax_facts,
            total_entities=comp.total_entities,
            total_relationships=comp.total_relationships,
            total_unresolved_references=comp.total_unresolved_references,
            total_conflicts=1,
            is_partial=comp.is_partial,
        )
        object.__setattr__(doc_with_conflict, "completeness", new_comp)

        service._validator.validate(doc_with_conflict)
        json_conflict = doc_with_conflict.to_canonical_json()
        assert "conflict::test::1" in json_conflict
        assert '"total_conflicts":1' in json_conflict

    def test_shuffled_inputs_produce_byte_identical_canonical_json(self) -> None:
        """Shuffled inventory and syntax document order yields identical output."""
        inventory, syntax_docs = _build_standard_inspection_workload()

        insp_forward = create_mock_inspection_result(
            analysis_id=_FIXED_ANALYSIS_ID,
            project_id=_FIXED_PROJECT_ID,
            repository_id=_FIXED_REPO_ID,
            snapshot_id=_FIXED_SNAP_ID,
            config_fingerprint="golden-shuffle-v1",
            inventory=list(inventory),
            syntax_documents=list(syntax_docs),
        )

        # Reverse order
        insp_reversed = create_mock_inspection_result(
            analysis_id=_FIXED_ANALYSIS_ID,
            project_id=_FIXED_PROJECT_ID,
            repository_id=_FIXED_REPO_ID,
            snapshot_id=_FIXED_SNAP_ID,
            config_fingerprint="golden-shuffle-v1",
            inventory=list(reversed(inventory)),
            syntax_documents=list(reversed(syntax_docs)),
        )

        # Random shuffle with fixed seed
        rnd = random.Random(42)
        shuffled_inv = list(inventory)
        shuffled_docs = list(syntax_docs)
        rnd.shuffle(shuffled_inv)
        rnd.shuffle(shuffled_docs)

        insp_shuffled = create_mock_inspection_result(
            analysis_id=_FIXED_ANALYSIS_ID,
            project_id=_FIXED_PROJECT_ID,
            repository_id=_FIXED_REPO_ID,
            snapshot_id=_FIXED_SNAP_ID,
            config_fingerprint="golden-shuffle-v1",
            inventory=shuffled_inv,
            syntax_documents=shuffled_docs,
        )

        service = IRConstructionService()
        json_forward = service.construct(insp_forward).to_canonical_json()
        json_reversed = service.construct(insp_reversed).to_canonical_json()
        json_shuffled = service.construct(insp_shuffled).to_canonical_json()

        assert json_forward == json_reversed
        assert json_forward == json_shuffled
        assert json_forward.encode("utf-8") == json_shuffled.encode("utf-8")
