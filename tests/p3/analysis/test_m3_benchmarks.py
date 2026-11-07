"""Empirical benchmark measurements for Phase 3 Module 3 (Intermediate Representation).

Measures transformation throughput, memory efficiency, entity/relationship scaling,
and canonical JSON serialization payload size across small, medium, and large synthetic
F2 inspection workloads to provide evidence for M3 numeric capacity limits.
"""

from __future__ import annotations

import time
import tracemalloc
from uuid import uuid4

import pytest

from backend.platform.analysis.inspection.model import (
    ArtifactAnalysisRole,
    ArtifactProcessingOutcome,
)
from backend.platform.analysis.ir import (
    IRConstructionService,
    IREntityKind,
    IRRelationshipKind,
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
    create_mock_reference_fact,
    create_mock_source_range,
    create_mock_syntax_document,
)


def _generate_synthetic_f2_workload(
    num_files: int,
    facts_per_file: int,
) -> tuple[int, object]:
    """Generate a synthetic F2 inspection result with scalable file & fact counts."""
    inventory = []
    syntax_docs = []
    total_facts = 0

    for i in range(num_files):
        path = f"src/module_{i:04d}.py"
        art_id = uuid4()
        entry = create_mock_inventory_entry(
            path=path,
            artifact_id=art_id,
            detected_language="python",
            role=ArtifactAnalysisRole.SEMANTIC,
            outcome=ArtifactProcessingOutcome.ANALYZED,
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
            size_bytes=facts_per_file * 64,
        )
        inventory.append(entry)

        declarations = []
        imports = []
        exports = []
        references = []

        # 40% declarations, 20% imports, 20% exports, 20% references
        num_decls = int(facts_per_file * 0.4)
        num_imports = int(facts_per_file * 0.2)
        num_exports = int(facts_per_file * 0.2)
        num_refs = facts_per_file - (num_decls + num_imports + num_exports)

        for d in range(num_decls):
            d_name = f"func_{d}"
            r_start = d * 30
            r_end = r_start + 25
            decl = create_mock_declaration_fact(
                fact_key=f"decl::{i}::{d}",
                name=d_name,
                kind=DeclarationKind.FUNCTION,
                declaration_range=create_mock_source_range(r_start, r_end),
                name_range=create_mock_source_range(r_start + 4, r_start + 10),
            )
            declarations.append(decl)

        for m in range(num_imports):
            imp = create_mock_import_fact(
                fact_key=f"imp::{i}::{m}",
                source_module=f"external_lib_{m}",
                imported_name=f"item_{m}",
                kind=ImportKind.NAMED,
            )
            imports.append(imp)

        for e in range(num_exports):
            exp_target = f"func_{e % max(num_decls, 1)}"
            exp = create_mock_export_fact(
                fact_key=f"exp::{i}::{e}",
                exported_name=exp_target,
                local_name=exp_target,
                kind=ExportKind.NAMED,
            )
            exports.append(exp)

        for r in range(num_refs):
            ref_target = f"func_{r % max(num_decls, 1)}"
            ref = create_mock_reference_fact(
                fact_key=f"ref::{i}::{r}",
                target_name=ref_target,
                kind=ReferenceKind.CALL,
            )
            references.append(ref)

        file_facts_count = (
            len(declarations) + len(imports) + len(exports) + len(references)
        )
        total_facts += file_facts_count

        s_doc = create_mock_syntax_document(
            path=path,
            language="python",
            artifact_id=art_id,
            declarations=declarations,
            imports=imports,
            exports=exports,
            references=references,
        )
        syntax_docs.append(s_doc)

    inspection = create_mock_inspection_result(
        inventory=inventory,
        syntax_documents=syntax_docs,
    )
    return total_facts, inspection


class TestIRM3Benchmarks:
    """Benchmark tests asserting performance characteristics and scaling limits."""

    def test_benchmark_small_workload(self) -> None:
        """Benchmark 20 files with 25 facts each (500 total facts)."""
        num_files = 20
        facts_per_file = 25
        total_facts, inspection = _generate_synthetic_f2_workload(
            num_files, facts_per_file
        )

        service = IRConstructionService()
        start = time.perf_counter()
        doc = service.construct(inspection)  # type: ignore[arg-type]
        duration = time.perf_counter() - start

        canon_json = doc.to_canonical_json()
        payload_bytes = len(canon_json.encode("utf-8"))

        assert duration < 2.0  # Safe non-flaky threshold
        assert doc.completeness.total_inventory_artifacts == num_files
        assert doc.completeness.total_syntax_facts == total_facts
        assert len(doc.entities) > num_files
        assert len(doc.relationships) > 0
        assert payload_bytes > 0

    def test_benchmark_medium_workload(self) -> None:
        """Benchmark 100 files with 20 facts each (2,000 total facts)."""
        num_files = 100
        facts_per_file = 20
        total_facts, inspection = _generate_synthetic_f2_workload(
            num_files, facts_per_file
        )

        service = IRConstructionService()
        start = time.perf_counter()
        doc = service.construct(inspection)  # type: ignore[arg-type]
        construction_time = time.perf_counter() - start

        start_ser = time.perf_counter()
        canon_json = doc.to_canonical_json()
        ser_time = time.perf_counter() - start_ser

        payload_bytes = len(canon_json.encode("utf-8"))
        facts_per_sec = total_facts / max(construction_time, 0.001)

        # Assert referential integrity of construction
        assert len(doc.entities) >= num_files * 8  # 1 module + declarations
        assert len(doc.relationships) >= num_files * 10
        assert doc.completeness.is_partial is False
        assert construction_time < 5.0
        assert ser_time < 2.0
        assert facts_per_sec > 500  # High normalization throughput
        assert payload_bytes < 10 * 1024 * 1024  # Well within 10 MB

    def test_benchmark_large_workload_evidence_for_caps(self) -> None:
        """Benchmark 250 files with 20 facts each (5,000 total facts).

        Produces empirical evidence for:
        1. Max entities per IR document
        2. Max relationships per IR document
        3. Canonical JSON serialized payload footprint
        """
        num_files = 250
        facts_per_file = 20
        total_facts, inspection = _generate_synthetic_f2_workload(
            num_files, facts_per_file
        )

        service = IRConstructionService()
        start = time.perf_counter()
        doc = service.construct(inspection)  # type: ignore[arg-type]
        construction_duration = time.perf_counter() - start

        start_ser = time.perf_counter()
        canon_json = doc.to_canonical_json()
        ser_duration = time.perf_counter() - start_ser

        payload_bytes = len(canon_json.encode("utf-8"))

        # Evidence observations
        entity_count = len(doc.entities)
        rel_count = len(doc.relationships)
        ev_count = len(doc.evidence)
        unres_count = len(doc.unresolved_references)

        assert construction_duration < 10.0
        assert ser_duration < 5.0
        assert entity_count > 2000
        assert rel_count > 4000
        assert ev_count > 5000
        assert unres_count > 500
        assert payload_bytes > 500_000

        # Verify key distributions
        artifact_entities = sum(
            1 for e in doc.entities if e.kind == IREntityKind.ARTIFACT
        )
        module_entities = sum(1 for e in doc.entities if e.kind == IREntityKind.MODULE)
        symbol_entities = sum(1 for e in doc.entities if e.kind == IREntityKind.SYMBOL)
        assert artifact_entities == num_files
        assert module_entities == num_files
        assert symbol_entities > 0

        declares_rels = sum(
            1 for r in doc.relationships if r.kind == IRRelationshipKind.DECLARES
        )
        assert declares_rels == symbol_entities

    def test_benchmark_scaled_workload_memory_evidence(self) -> None:
        """Benchmark 500 files with 50 facts each (25,000 total facts).

        Measures peak memory using tracemalloc to provide realistic memory/throughput
        evidence under heavy repository loads.
        """
        num_files = 500
        facts_per_file = 50
        total_facts, inspection = _generate_synthetic_f2_workload(
            num_files, facts_per_file
        )

        service = IRConstructionService()

        tracemalloc.start()
        start = time.perf_counter()
        doc = service.construct(inspection)  # type: ignore[arg-type]
        construction_duration = time.perf_counter() - start
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_memory / (1024 * 1024)

        # 25k facts normalized within generous limits
        assert construction_duration < 35.0
        assert peak_mb < 250.0  # Peak memory well under 250 MB
        assert len(doc.entities) >= 10000
        assert len(doc.relationships) >= 20000
        assert doc.completeness.total_syntax_facts == total_facts

    @pytest.mark.slow
    def test_benchmark_worst_case_legal_workload(self) -> None:
        """Benchmark legal worst case of 250,000 facts across 1,000 files.

        Empirically verifies that the legal F2 upper bound
        (parser_max_facts_per_analysis) constructs safely and fits
        comfortably within approved capacity limits.
        """
        num_files = 1000
        facts_per_file = 250
        total_facts, inspection = _generate_synthetic_f2_workload(
            num_files, facts_per_file
        )

        service = IRConstructionService()

        tracemalloc.start()
        start = time.perf_counter()
        doc = service.construct(inspection)  # type: ignore[arg-type]
        construction_duration = time.perf_counter() - start
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_memory / (1024 * 1024)

        canon_json = doc.to_canonical_json()
        payload_bytes = len(canon_json.encode("utf-8"))

        print(
            f"\n[WORST-CASE BENCHMARK] "
            f"Duration: {construction_duration:.2f}s | "
            f"Peak tracemalloc: {peak_mb:.2f} MB | "
            f"Entities: {len(doc.entities)} | "
            f"Relationships: {len(doc.relationships)} | "
            f"Evidence: {len(doc.evidence)} | "
            f"Unresolved: {len(doc.unresolved_references)} | "
            f"Payload: {payload_bytes} bytes ({payload_bytes / (1024 * 1024):.2f} MB)"
        )

        assert total_facts == 250_000
        assert construction_duration < 600.0  # Bounded by stage timeout
        assert peak_mb < 2000.0
        # Assert within updated capacity limits
        assert len(doc.entities) <= 150_000
        assert len(doc.relationships) <= 500_000
        assert len(doc.evidence) <= 500_000
        assert len(doc.unresolved_references) <= 150_000
        assert payload_bytes <= 512 * 1024 * 1024
