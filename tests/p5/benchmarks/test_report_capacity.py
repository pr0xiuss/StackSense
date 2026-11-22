"""Opt-in capacity benchmarks and limit boundary tests for Architecture Report."""

from __future__ import annotations

import time
from uuid import uuid4

from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.preparation import ReportPreparer
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


def test_capacity_typical_workload() -> None:
    """Measure duration under typical workload (200 entities, 100 diagnostics)."""
    context, diagrams = sample_work_context()

    class BenchmarkArchitectureService(FakeArchitectureQueryService):
        def list_entities(self, version_id, project_id, *, limit, offset):
            class Entity:
                def __init__(self, i):
                    self.id = uuid4()
                    self.logical_id = f"entity_{i}"
                    self.kind = "service" if i % 2 == 0 else "endpoint"
                    self.status = "confirmed"

            class Collection:
                items = [Entity(i) for i in range(min(limit, 200))]
                total = 200

            return Collection()

    class BenchmarkLifecycleService(FakeAnalysisLifecycleService):
        def list_diagnostics(self, analysis_id, project_id, *, limit=100, offset=0):
            from datetime import UTC, datetime

            class Diag:
                def __init__(self, i):
                    self.id = uuid4()
                    self.code = f"WARN_{i}"
                    self.category = "security"
                    self.severity = "warning"
                    self.scope = "file"
                    self.stage = "analysis"
                    self.message = f"Capacity test diagnostic #{i} with detail payload."
                    self.artifact_path = f"src/bench_{i}.py"
                    self.source_line = i
                    self.source_column = 1
                    self.created_at = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)
                    self.retryability = "non_retryable"
                    self.withheld_reason = None

            total_diags = 100
            start = offset
            end = min(offset + limit, total_diags)

            class ListRes:
                items = [Diag(i) for i in range(start, end)]
                total = total_diags

            return ListRes()

    preparer = ReportPreparer(
        architecture_query=BenchmarkArchitectureService(),
        analysis_lifecycle=BenchmarkLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )

    t0 = time.perf_counter()
    spec, snapshot, prepared_report = preparer.prepare(context)
    prep_duration = time.perf_counter() - t0

    assert prep_duration < 10.0  # Well within 120s limit
    assert len(spec.sections[3].diagnostics) == 100  # type: ignore[attr-defined]

    renderer = ReportLabPdfRenderer()
    t1 = time.perf_counter()
    rendered = renderer.render(prepared_report, deadline=time.monotonic() + 30.0)
    render_duration = time.perf_counter() - t1

    assert render_duration < 15.0  # Well within 60s limit
    assert rendered.page_count >= 5
    assert rendered.size_bytes < 5 * 1024 * 1024  # Well under 32 MiB ceiling
