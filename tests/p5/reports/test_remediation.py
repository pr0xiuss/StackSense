"""Regression reproductions for REV-001–017. Unit proofs are not PG/OS proofs."""

import hashlib
import io
from datetime import UTC, datetime
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.delivery.publication import (
    GuardedEnlistedSession,
    PublicationContext,
    PublicationGuard,
)
from backend.platform.reports.artifacts import CandidateReportWriter
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import DiagnosticsSection, ReportSpec
from backend.platform.reports.model import c4_canonical_bytes, c4_report_spec_digest
from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.persistence import REPORT_TABLES
from backend.platform.reports.preparation import ReportPreparer
from backend.platform.reports.repository import (
    ReportDatabaseReadAuthority,
    ReportPublicationPort,
)
from backend.platform.reports.service import ReportWorkHandler
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


@pytest.fixture
def inputs():
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        FakeArchitectureQueryService(),
        FakeAnalysisLifecycleService(),
        FakeDiagramReader(diagrams),
    )
    return context, preparer, preparer.prepare(context)[2]


def test_deep_immutability_and_serialization_revalidation(inputs):
    _, _, prepared = inputs
    provenance = prepared.spec.diagram_inputs[0].provenance
    with pytest.raises(ValidationError):
        provenance.diagram_id = "changed"
    broken = prepared.spec.model_copy(update={"report_spec_digest": "0" * 64})
    with pytest.raises(ValueError):
        broken.to_bytes()
    with pytest.raises(ValueError):
        c4_canonical_bytes({"value": 1.5})
    with pytest.raises(ValueError):
        ReportSpec.from_bytes(b'{"c4_version":"1.0.0","c4_version":"1.0.0"}')


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_pdf_bytes", 10**12),
        ("max_pdf_pages", 257),
        ("render_timeout_seconds", 121),
        ("hard_max_pdf_pages", 300),
        ("child_memory_limit_mb", 1025),
    ],
)
def test_hard_limits_cannot_be_relaxed(field, value):
    with pytest.raises(ValueError):
        ReportLimits(**{field: value})


def test_all_diagnostics_and_literal_markup_are_preserved(inputs):
    _, _, prepared = inputs
    source = next(
        s for s in prepared.spec.sections if isinstance(s, DiagnosticsSection)
    )
    diagnostics = tuple(
        source.diagnostics[0].model_copy(
            update={
                "diagnostic_id": uuid4(),
                "code": f"MARKER_{i}",
                "message": f"LONG_{i} "
                + "word " * 80
                + f"END_{i} <link href='https://example.invalid'>literal</link>",
            }
        )
        for i in range(35)
    )
    spec = prepared.spec.model_copy(
        update={
            "sections": tuple(
                (
                    s.model_copy(update={"diagnostics": diagnostics})
                    if isinstance(s, DiagnosticsSection)
                    else s
                )
                for s in prepared.spec.sections
            )
        }
    )
    spec = spec.model_copy(update={"report_spec_digest": c4_report_spec_digest(spec)})
    result = ReportLabPdfRenderer().render(
        prepared.model_copy(update={"spec": spec}), monotonic() + 30
    )
    pdf = PdfReader(io.BytesIO(result.pdf_bytes))
    text = "\n".join(page.extract_text() for page in pdf.pages)
    assert all(f"END_{i}" in text for i in range(35))
    assert all(not page.get("/Annots") for page in pdf.pages)


def test_pdf_validator_resolves_indirect_prohibited_actions(inputs):
    _, _, prepared = inputs
    writer = PdfWriter()
    writer.add_blank_page(595, 842)
    writer._root_object[NameObject("/OpenAction")] = writer._add_object(
        DictionaryObject(
            {
                NameObject("/S"): NameObject("/JavaScript"),
                NameObject("/JS"): TextStringObject("app.alert('bad')"),
            }
        )
    )
    stream = io.BytesIO()
    writer.write(stream)
    with pytest.raises(ValueError):
        ReportLabPdfRenderer()._validate_rendered_pdf(stream.getvalue(), prepared.spec)


def test_snapshot_replay_after_committed_staging_and_exact_reference(inputs, tmp_path):
    context, preparer, _ = inputs
    engine = create_engine("sqlite:///:memory:")
    for table in REPORT_TABLES:
        table.create(engine, checkfirst=True)
    calls = []
    original = preparer.prepare

    def counted(ctx):
        calls.append(1)
        return original(ctx)

    preparer.prepare = counted

    class Stop:
        def render(self, *args, **kwargs):
            raise RuntimeError("simulated crash")

    def writer(att, cid, aid, limits):
        return CandidateReportWriter(att, cid, aid, limits, tmp_path)

    handler = ReportWorkHandler(
        binding=context.attempt.work.binding,
        engine_or_session=engine,
        preparer=preparer,
        renderer=Stop(),
        writer_factory=writer,
    )
    with pytest.raises(RuntimeError):
        handler._execute(context, monotonic() + 30)
    handler.renderer = ReportLabPdfRenderer()
    output = handler._execute(context, monotonic() + 30)
    assert calls == [1]
    assert handler._execute(context, monotonic() + 30) == output
    assert calls == [1]
    with Session(engine) as session:
        port = ReportPublicationPort(
            GuardedEnlistedSession(
                session, guard=PublicationGuard(), check=lambda: None
            )
        )
        accepted = port.publish_prepared(
            output,
            PublicationContext(
                transaction_id=uuid4(),
                attempt=context.attempt,
                deadline=datetime.now(UTC),
            ),
        )
        session.commit()
    authority = ReportDatabaseReadAuthority(engine, ReportLimits())
    foreign = context.attempt.work.scope.model_copy(update={"project_id": uuid4()})
    with Session(engine) as session, pytest.raises(ValueError):
        authority._exact(
            session, foreign, accepted.reference.model_copy(update={"scope": foreign})
        )
    with Session(engine) as session, pytest.raises(ValueError):
        authority._exact(
            session,
            context.attempt.work.scope,
            accepted.reference.model_copy(update={"artifact_id": uuid4()}),
        )
    path = tmp_path / "sealed" / str(output.candidate.generation_id) / "report.pdf"
    original_bytes = path.read_bytes()
    spec, _, prepared = original(context)
    w = writer(
        context.attempt,
        output.candidate.generation_id,
        output.candidate.artifact_id,
        ReportLimits(),
    )
    w.require_staging = lambda attempt: None
    with pytest.raises(ValueError):
        w.stage_artifacts(
            spec,
            b"replacement",
            hashlib.sha256(b"replacement").hexdigest(),
            1,
            spec.metadata.source_snapshot_digest,
            prepared.renderer_profile_digest,
            prepared.limits_digest,
            "1" * 64,
        )
    assert path.read_bytes() == original_bytes
    engine.dispose()


def test_full_canonical_pagination_and_actual_coverage(inputs):
    context, preparer, _ = inputs

    class Source(FakeArchitectureQueryService):
        def list_entities(self, version, project, *, limit, offset):
            return SimpleNamespace(
                total=350,
                items=[
                    SimpleNamespace(
                        id=uuid4(),
                        logical_id=f"service_{i:04d}",
                        kind="service",
                        status="inferred",
                    )
                    for i in range(offset, min(offset + limit, 350))
                ],
            )

    preparer.architecture_query = Source()
    spec, _, _ = preparer.prepare(context)
    assert spec.coverage.total_entities == 350
    assert spec.sections[1].counts_by_kind == (("service", 350),)
    assert spec.coverage.selected_inventory_count == 200
    assert spec.coverage.omitted_inventory_count == 150
    assert spec.coverage.persisted_coverage is None


def test_actual_render_child_killed_and_reaped_at_deadline(inputs, monkeypatch):
    import backend.platform.reports.render_runtime as runtime

    _, _, prepared = inputs
    children = []
    popen = runtime.subprocess.Popen

    def tracked(*args, **kwargs):
        process = popen(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(runtime.subprocess, "Popen", tracked)
    monkeypatch.setattr(
        runtime,
        "_CHILD",
        runtime._CHILD.replace(
            "result = ReportLabPdfRenderer(limits).render(prepared, DEADLINE)",
            "while True: pass",
        ),
    )
    start = monotonic()
    with pytest.raises(TimeoutError):
        runtime.IsolatedReportRenderRuntime().execute_render(
            prepared, timeout_seconds=2
        )
    assert monotonic() - start < 4
    assert children and all(p.poll() is not None for p in children)


def test_actual_child_cannot_open_inputs_network_or_inherit_credentials(
    inputs, monkeypatch
):
    import backend.platform.reports.render_runtime as runtime

    _, _, prepared = inputs
    monkeypatch.setenv("STACKSENSE_REVIEW_SECRET", "must-not-inherit")
    probe = """
assert 'STACKSENSE_REVIEW_SECRET' not in os.environ
for action in (lambda: socket.create_connection(('127.0.0.1',9)),
               lambda: open('/etc/passwd'), lambda: os.open('/etc/passwd',0)):
    try: action()
    except PermissionError: pass
    else: raise AssertionError('renderer IO allowed')
"""
    monkeypatch.setattr(
        runtime,
        "_CHILD",
        runtime._CHILD.replace(
            "result = ReportLabPdfRenderer(limits).render(prepared, DEADLINE)",
            probe
            + "\nresult = ReportLabPdfRenderer(limits).render(prepared, DEADLINE)",
        ),
    )
    result = runtime.IsolatedReportRenderRuntime().execute_render(prepared)
    assert result.pdf_bytes.startswith(b"%PDF-")


def test_actual_child_memory_exhaustion_fails_without_output(inputs, monkeypatch):
    import backend.platform.reports.render_runtime as runtime

    _, _, prepared = inputs
    monkeypatch.setattr(
        runtime,
        "_CHILD",
        runtime._CHILD.replace(
            "result = ReportLabPdfRenderer(limits).render(prepared, DEADLINE)",
            "memory = bytearray(2*1024*1024*1024)",
        ),
    )
    with pytest.raises(ValueError, match="report_render_failed"):
        runtime.IsolatedReportRenderRuntime().execute_render(prepared)
