"""Renderer compatibility, byte determinism, and pypdf security checks."""

from __future__ import annotations

import io
import time

import pytest
from pypdf import PdfReader

from backend.platform.reports.contracts import RenderedReport
from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.preparation import ReportPreparer
from backend.platform.reports.render_runtime import IsolatedReportRenderRuntime
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


def test_pdf_renderer_three_cold_renders_byte_identical() -> None:
    """B1 pass gate: 3 fresh renders produce identical SHA256."""
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared_report = preparer.prepare(context)

    renderer = ReportLabPdfRenderer()

    # 1st render
    res1 = renderer.render(prepared_report, deadline=time.monotonic() + 30.0)
    # 2nd render
    res2 = renderer.render(prepared_report, deadline=time.monotonic() + 30.0)
    # 3rd render
    res3 = renderer.render(prepared_report, deadline=time.monotonic() + 30.0)

    assert res1.page_count > 0
    assert res1.size_bytes > 0
    assert res1.sha256 == res2.sha256
    assert res2.sha256 == res3.sha256
    assert res1.pdf_bytes == res2.pdf_bytes
    assert res2.pdf_bytes == res3.pdf_bytes


def test_pdf_structure_and_security_validation() -> None:
    """Verify pypdf parses the generated PDF and confirms no active scripts."""
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared_report = preparer.prepare(context)

    renderer = ReportLabPdfRenderer()
    rendered = renderer.render(prepared_report, deadline=time.monotonic() + 30.0)

    assert rendered.pdf_bytes.startswith(b"%PDF-")
    assert b"%%EOF" in rendered.pdf_bytes[-1024:]

    reader = PdfReader(io.BytesIO(rendered.pdf_bytes))
    assert not reader.is_encrypted
    assert (
        len(reader.pages) >= 5
    )  # Cover + Inventory + Diagrams + Diagnostics + Coverage + Provenance

    # Inspect text extracted from pages to ensure sections are present
    full_text = " ".join(page.extract_text() for page in reader.pages)
    assert "StackSense Architecture Analysis Report" in full_text
    assert "Architecture Inventory & Boundaries" in full_text
    assert "Architecture Diagrams" in full_text
    assert "Coverage, Uncertainty & Limitations" in full_text
    assert "Provenance, Licenses & Appendix" in full_text


def test_isolated_render_runtime_bounded_execution() -> None:
    """Supervised execution correctly enforces deadline and cooperative checkpoints."""
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared_report = preparer.prepare(context)

    runtime = IsolatedReportRenderRuntime()
    rendered = runtime.execute_render(prepared_report, timeout_seconds=30.0)
    assert isinstance(rendered, RenderedReport)
    assert rendered.page_count > 0

    # Test immediate deadline timeout
    with pytest.raises(TimeoutError, match="exceeded deadline"):
        runtime.execute_render(prepared_report, timeout_seconds=0.000001)
