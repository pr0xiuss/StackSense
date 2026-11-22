"""Unit tests for ReportValidator and C4 specification validation."""

from __future__ import annotations

import pytest

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.reports.contracts import (
    DiagramsSection,
    ReportContractError,
)
from backend.platform.reports.preparation import ReportPreparer
from backend.platform.reports.validation import ReportValidator
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


def test_report_validator_accepts_valid_spec() -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, _, _ = preparer.prepare(context)

    validator = ReportValidator()
    # Should validate without error
    validator.validate(spec)


def test_report_validator_rejects_corrupted_spec_digest() -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, _, _ = preparer.prepare(context)

    corrupted_spec = spec.model_copy(update={"report_spec_digest": "0" * 64})
    validator = ReportValidator()
    with pytest.raises(ReportContractError, match="Report spec digest mismatch"):
        validator.validate(corrupted_spec)


def test_report_validator_rejects_missing_diagram_placement() -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, _, _ = preparer.prepare(context)

    # Filter out DATA_FLOW placement from DiagramsSection
    sec_list = list(spec.sections)
    diag_sec = sec_list[2]
    assert isinstance(diag_sec, DiagramsSection)
    filtered_placements = tuple(
        p for p in diag_sec.placements if p.template != DiagramTemplate.DATA_FLOW
    )
    new_diag_sec = diag_sec.model_copy(update={"placements": filtered_placements})
    sec_list[2] = new_diag_sec
    bad_spec = spec.model_copy(update={"sections": tuple(sec_list)})

    validator = ReportValidator()
    with pytest.raises(ReportContractError, match="has no page placement"):
        validator.validate(bad_spec)


def test_report_validator_rejects_duplicate_slot_on_same_page() -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, _, _ = preparer.prepare(context)

    sec_list = list(spec.sections)
    diag_sec = sec_list[2]
    assert isinstance(diag_sec, DiagramsSection)
    p0 = diag_sec.placements[0]
    # Create duplicate placement with same page_index and slot_id
    duplicate_p = p0.model_copy()
    new_diag_sec = diag_sec.model_copy(
        update={"placements": diag_sec.placements + (duplicate_p,)}
    )
    sec_list[2] = new_diag_sec
    bad_spec = spec.model_copy(update={"sections": tuple(sec_list)})

    validator = ReportValidator()
    with pytest.raises(ReportContractError, match="Duplicate slot"):
        validator.validate(bad_spec)
