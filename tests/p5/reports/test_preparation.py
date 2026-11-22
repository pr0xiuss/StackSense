"""Unit tests for ReportPreparer and C4 input capture."""

from __future__ import annotations

import pytest

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.reports.contracts import (
    CoverageSection,
    DiagnosticsSection,
    DiagramsSection,
    InventorySection,
    MetadataSection,
    ProvenanceSection,
)
from backend.platform.reports.preparation import ReportPreparer
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


def test_report_preparer_end_to_end() -> None:
    context, diagrams = sample_work_context()
    arch_query = FakeArchitectureQueryService()
    analysis_lifecycle = FakeAnalysisLifecycleService()
    diag_reader = FakeDiagramReader(diagrams)

    preparer = ReportPreparer(
        architecture_query=arch_query,
        analysis_lifecycle=analysis_lifecycle,
        diagram_reader=diag_reader,
    )

    spec, snapshot, prepared_report = preparer.prepare(context)

    # 1. Check spec integrity
    assert spec.c4_version == "1.0.0"
    assert spec.report_type == "architecture_analysis"
    assert len(spec.sections) == 6
    assert isinstance(spec.sections[0], MetadataSection)
    assert isinstance(spec.sections[1], InventorySection)
    assert isinstance(spec.sections[2], DiagramsSection)
    assert isinstance(spec.sections[3], DiagnosticsSection)
    assert isinstance(spec.sections[4], CoverageSection)
    assert isinstance(spec.sections[5], ProvenanceSection)

    # 2. Check all 4 diagrams in order
    assert len(spec.diagram_inputs) == 4
    assert spec.diagram_inputs[0].template == DiagramTemplate.OVERVIEW
    assert spec.diagram_inputs[1].template == DiagramTemplate.COMPONENT
    assert spec.diagram_inputs[2].template == DiagramTemplate.DEPENDENCY
    assert spec.diagram_inputs[3].template == DiagramTemplate.DATA_FLOW

    # 3. Check diagnostics
    diag_section = spec.sections[3]
    assert isinstance(diag_section, DiagnosticsSection)
    assert len(diag_section.diagnostics) == 6
    assert all(
        d.severity in ("info", "warning", "error", "critical")
        for d in diag_section.diagnostics
    )

    # 4. Check snapshot
    assert snapshot.snapshot_size_bytes > 0
    assert len(snapshot.snapshot_digest) == 64
    assert len(snapshot.font_assets) == 2
    assert len(snapshot.diagram_assets) == 4

    # 5. Check prepared report
    assert prepared_report.spec == spec
    assert len(prepared_report.page_placements) == 4


def test_report_preparer_fails_on_missing_diagram() -> None:
    context, diagrams = sample_work_context()
    # Remove one required diagram from the reader
    del diagrams[DiagramTemplate.DATA_FLOW]
    arch_query = FakeArchitectureQueryService()
    analysis_lifecycle = FakeAnalysisLifecycleService()
    diag_reader = FakeDiagramReader(diagrams)

    preparer = ReportPreparer(
        architecture_query=arch_query,
        analysis_lifecycle=analysis_lifecycle,
        diagram_reader=diag_reader,
    )

    with pytest.raises(ValueError, match="diagram_not_found"):
        preparer.prepare(context)
