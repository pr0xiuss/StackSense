"""Unit tests for C4 v1.0.0 contracts, immutability, and canonical serialization."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.platform.reports.contracts import (
    CoverageSection,
    DiagnosticsSection,
    DiagramsSection,
    InventorySection,
    MetadataSection,
    ProvenanceSection,
    ReportContractError,
    ReportCoverage,
    ReportDiagnostic,
    ReportMetadata,
    ReportSourceRef,
    ReportSpec,
)
from backend.platform.reports.model import (
    c4_canonical_json,
    c4_report_resource_id,
)
from tests.p5.reports.conftest import (
    sample_barrier_receipt,
    sample_handler_profile,
    sample_scope,
)


def test_frozen_report_models_reject_mutation() -> None:
    scope = sample_scope()
    ref = ReportSourceRef(
        source_kind="entity",
        architecture_version_id=scope.architecture_version_id,
        logical_id="test_service",
    )
    with pytest.raises(ValidationError):
        ref.logical_id = "mutated"  # type: ignore[misc]


def test_report_diagnostic_original_severity_preserved() -> None:
    ref = ReportSourceRef(source_kind="analysis_diagnostic")
    diag = ReportDiagnostic(
        diagnostic_id=UUID("00000000-0000-0000-0000-000000000010"),
        source_ref=ref,
        severity="critical",
        code="SEC001",
        category="security",
        scope="file",
        stage="analysis",
        message="Critical security vulnerability detected",
        created_at=datetime(2026, 11, 20, 10, 0, 0, tzinfo=UTC),
        retryability="non_retryable",
    )
    assert diag.severity == "critical"
    assert diag.code == "SEC001"

    # Invalid severity should be rejected by Pydantic
    with pytest.raises(ValidationError):
        ReportDiagnostic(
            diagnostic_id=UUID("00000000-0000-0000-0000-000000000010"),
            source_ref=ref,
            severity="extreme_danger",  # type: ignore[arg-type]
            code="SEC001",
            category="security",
            scope="file",
            stage="analysis",
            message="bad",
            created_at=datetime(2026, 11, 20, 10, 0, 0, tzinfo=UTC),
            retryability="non_retryable",
        )


def test_c4_canonical_json_determinism() -> None:
    data1 = {"b": 2, "a": 1, "c": [3, 2, 1], "d": True, "e": None}
    data2 = {"e": None, "a": 1, "d": True, "c": [3, 2, 1], "b": 2}
    json1 = c4_canonical_json(data1)
    json2 = c4_canonical_json(data2)
    assert json1 == json2
    assert json1 == '{"a":1,"b":2,"c":[3,2,1],"d":true,"e":null}'


def test_c4_report_resource_id_deterministic() -> None:
    scope = sample_scope()
    binding = sample_handler_profile()
    fingerprint = "0123456789abcdef" * 4
    id1 = c4_report_resource_id(scope, binding, fingerprint)
    id2 = c4_report_resource_id(scope, binding, fingerprint)
    assert id1 == id2
    assert isinstance(id1, UUID)

    # Different fingerprint produces different resource UUID
    id3 = c4_report_resource_id(scope, binding, "fedcba9876543210" * 4)
    assert id1 != id3


def test_report_spec_enforces_exact_four_ordered_diagrams() -> None:
    scope = sample_scope()
    barrier, diagrams = sample_barrier_receipt(scope)
    meta = ReportMetadata(
        report_id=UUID("00000000-0000-0000-0000-000000000099"),
        scope=scope,
        profile=sample_handler_profile(),
        captured_at=datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC),
        source_snapshot_digest="0" * 64,
        renderer_version="5.1.0",
        font_version="dejavu_paths_2_37_v1",
        asset_manifest_digest="f" * 64,
    )
    coverage = ReportCoverage(
        total_entities=10,
        total_relationships=5,
        total_evidence=15,
        total_unresolved=0,
        total_conflicts=0,
        analysis_status="completed",
        selected_inventory_count=10,
        omitted_inventory_count=0,
        selected_diagnostic_count=0,
        omitted_diagnostic_count=0,
        selected_reference_count=15,
        omitted_reference_count=0,
    )
    sec1 = MetadataSection(metadata=meta)
    sec2 = InventorySection(
        counts_by_kind=(),
        counts_by_status=(),
        relationship_counts_by_kind=(),
        selected_entities=(),
        selected_relationships=(),
        selected_count=0,
        omitted_count=0,
    )
    sec3 = DiagramsSection(diagram_inputs=(), placements=())
    sec4 = DiagnosticsSection(diagnostics=())
    sec5 = CoverageSection(coverage=coverage)
    sec6 = ProvenanceSection(
        source_snapshot_digest="0" * 64,
        diagram_receipts=(),
        font_licenses=(),
        selection_policy="test",
        omitted_totals={},
    )

    # Missing diagram inputs (empty) must raise ReportContractError
    with pytest.raises(
        (ReportContractError, ValidationError), match="exactly four diagram inputs"
    ):
        ReportSpec(
            metadata=meta,
            sections=(sec1, sec2, sec3, sec4, sec5, sec6),
            diagram_inputs=(),
            coverage=coverage,
        )


def test_report_spec_enforces_section_order() -> None:
    scope = sample_scope()
    meta = ReportMetadata(
        report_id=UUID("00000000-0000-0000-0000-000000000099"),
        scope=scope,
        profile=sample_handler_profile(),
        captured_at=datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC),
        source_snapshot_digest="0" * 64,
        renderer_version="5.1.0",
        font_version="dejavu_paths_2_37_v1",
        asset_manifest_digest="f" * 64,
    )
    coverage = ReportCoverage(
        total_entities=0,
        total_relationships=0,
        total_evidence=0,
        total_unresolved=0,
        total_conflicts=0,
        analysis_status="completed",
        selected_inventory_count=0,
        omitted_inventory_count=0,
        selected_diagnostic_count=0,
        omitted_diagnostic_count=0,
        selected_reference_count=0,
        omitted_reference_count=0,
    )
    sec1 = MetadataSection(metadata=meta)
    sec2 = InventorySection(
        counts_by_kind=(),
        counts_by_status=(),
        relationship_counts_by_kind=(),
        selected_entities=(),
        selected_relationships=(),
        selected_count=0,
        omitted_count=0,
    )
    sec4 = DiagnosticsSection(diagnostics=())

    # Wrong section order must fail validation
    with pytest.raises(
        (ReportContractError, ValidationError), match="Sections must be exactly"
    ):
        ReportSpec(
            metadata=meta,
            sections=(sec2, sec1, sec4),  # wrong order and missing
            diagram_inputs=(),
            coverage=coverage,
        )
