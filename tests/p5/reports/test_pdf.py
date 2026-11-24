"""Tests for complete PDF renderer, vector drawing, pagination, and security."""

from __future__ import annotations

import io
import time

import pytest
from pypdf import PdfReader

from backend.platform.reports.contracts import (
    DiagramsSection,
    InventorySection,
    RenderedReport,
)
from backend.platform.reports.model import c4_report_spec_digest
from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.preparation import ReportPreparer
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


def test_pdf_renderer_produces_valid_structure() -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared = preparer.prepare(context)
    renderer = ReportLabPdfRenderer()

    rendered = renderer.render(prepared, deadline=time.monotonic() + 30.0)

    assert isinstance(rendered, RenderedReport)
    assert rendered.media_type == "application/pdf"
    assert rendered.page_count >= 5
    assert rendered.size_bytes > 0
    assert len(rendered.sha256) == 64

    # Validate with pypdf
    reader = PdfReader(io.BytesIO(rendered.pdf_bytes))
    assert len(reader.pages) == rendered.page_count
    assert not reader.is_encrypted


def test_pdf_renderer_full_page_fallback() -> None:
    """When compact slots fail readability, paginates each diagram to full page."""
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared = preparer.prepare(context)

    # Force full page placement
    placements = preparer._compute_placements(spec.diagram_inputs, compact=False)
    sections = list(spec.sections)
    for i, s in enumerate(sections):
        if isinstance(s, DiagramsSection):
            sections[i] = DiagramsSection(
                diagram_inputs=s.diagram_inputs,
                placements=tuple(placements),
            )
    spec = spec.model_copy(update={"sections": tuple(sections)})
    spec = spec.model_copy(update={"report_spec_digest": c4_report_spec_digest(spec)})
    prepared_full = prepared.model_copy(
        update={
            "spec": spec,
            "page_placements": tuple(placements),
        }
    )

    renderer = ReportLabPdfRenderer()
    rendered = renderer.render(prepared_full, deadline=time.monotonic() + 30.0)

    assert rendered.page_count >= 7  # 4 diagram pages + cover + inv + diag + cov + prov


def test_pdf_renderer_unicode_and_escaping() -> None:
    """Verify renderer handles non-ASCII characters without raising or crashing."""
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared = preparer.prepare(context)

    # Add unicode text to inventory section
    sections = list(spec.sections)
    for i, s in enumerate(sections):
        if isinstance(s, InventorySection):
            items = list(s.selected_entities)
            if items:
                items[0] = items[0].model_copy(
                    update={"logical_id": "service_тест_alpha_Ω_🚀"}
                )
            sections[i] = s.model_copy(update={"selected_entities": tuple(items)})

    spec = spec.model_copy(update={"sections": tuple(sections)})
    spec = spec.model_copy(update={"report_spec_digest": c4_report_spec_digest(spec)})
    prepared_uni = prepared.model_copy(update={"spec": spec})

    renderer = ReportLabPdfRenderer()
    rendered = renderer.render(prepared_uni, deadline=time.monotonic() + 30.0)
    assert rendered.size_bytes > 0


def test_pdf_renderer_deadline_exceeded() -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared = preparer.prepare(context)
    renderer = ReportLabPdfRenderer()

    # Past deadline
    with pytest.raises(TimeoutError):
        renderer.render(prepared, deadline=time.monotonic() - 1.0)
