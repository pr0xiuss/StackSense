"""End-to-end integration test for the C4 Architecture Analysis Report pipeline.

Validates the full chain:
4 published diagram receipts -> M1 barrier context -> ReportWorkHandler.execute
-> PDF vector rendering -> CandidateReportWriter sealing -> M1 publication port
-> LocalReportArtifactStore verified readback.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    DeliveryExecutionFailure,
)
from backend.platform.delivery.publication import (
    GuardedEnlistedSession,
    PublicationContext,
    PublicationGuard,
)
from backend.platform.reports.artifacts import (
    CandidateReportWriter,
    LocalReportArtifactStore,
)
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.persistence import (
    REPORT_TABLES,
)
from backend.platform.reports.persistence import (
    ReportGenerationModel as Generation,
)
from backend.platform.reports.persistence import (
    ReportResourceModel as Resource,
)
from backend.platform.reports.preparation import ReportPreparer
from backend.platform.reports.repository import (
    ReportDatabaseReadAuthority,
    ReportPublicationPort,
)
from backend.platform.reports.service import (
    ReportReader,
    ReportWorkHandler,
)
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    for table in REPORT_TABLES:
        table.create(engine, checkfirst=True)
    yield engine
    engine.dispose()


def test_report_pipeline_end_to_end(test_db, tmp_path) -> None:
    context, diagrams = sample_work_context()
    limits = ReportLimits()

    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    renderer = ReportLabPdfRenderer()

    def writer_factory(att, cid, aid, lim):
        return CandidateReportWriter(
            attempt=att,
            candidate_id=cid,
            artifact_id=aid,
            limits=lim,
            root=tmp_path,
        )

    handler = ReportWorkHandler(
        binding=context.attempt.work.binding,
        engine_or_session=test_db,
        preparer=preparer,
        renderer=renderer,
        limits=limits,
        writer_factory=writer_factory,
    )

    # 1. Execute report work handler (C0 worker phase)
    prepared_output = handler.execute(context)
    assert prepared_output.attempt == context.attempt
    candidate_id = context.attempt.candidate_id
    assert prepared_output.candidate.generation_id == candidate_id
    assert prepared_output.candidate.sealed is True

    # Check candidate artifacts staged and sealed on disk
    sealed_dir = tmp_path / "sealed" / str(candidate_id)
    assert sealed_dir.exists()
    assert (sealed_dir / "manifest.json").exists()
    assert (sealed_dir / "report.pdf").exists()
    assert (sealed_dir / "report-spec.json").exists()

    # 2. Check generation state in database is SEALED_VERIFIED
    with Session(test_db) as session:
        gen = session.get(Generation, candidate_id)
        assert gen is not None
        assert gen.state == "SEALED_VERIFIED"
        assert gen.manifest_size == prepared_output.candidate.size_bytes
        assert gen.pdf_size is not None
        assert gen.page_count is not None
        assert gen.page_count >= 1

    # 3. Simulate M1 PublicationUnitOfWork enlisted transaction
    with Session(test_db) as session:
        guard = PublicationGuard()
        enlisted = GuardedEnlistedSession(session, guard=guard, check=lambda: None)
        pub_port = ReportPublicationPort(enlisted)

        pub_ctx = PublicationContext(
            transaction_id=uuid4(),
            attempt=context.attempt,
            deadline=datetime.now(UTC),
        )

        accepted_output = pub_port.publish_prepared(prepared_output, pub_ctx)
        session.commit()

        assert accepted_output.reference.generation_id == candidate_id
        assert accepted_output.reference.sealed is True

        # Generation is now ACCEPTED
        gen_after = session.get(Generation, candidate_id)
        assert gen_after.state == "ACCEPTED"
        assert gen_after.accepted_at is not None

        # Resource points to active generation
        res_after = session.get(Resource, gen_after.resource_id)
        assert res_after.accepted_generation_id == candidate_id

        # validate_ready passes on published reference
        pub_port.validate_ready(accepted_output.reference, pub_ctx)

    # 4. Verified readback through ReportReader and LocalReportArtifactStore
    read_authority = ReportDatabaseReadAuthority(test_db, limits=limits)
    store = LocalReportArtifactStore(
        authority=read_authority, limits=limits, root=tmp_path
    )
    reader = ReportReader(store=store, limits=limits)

    # Read verified spec
    spec, manifest = reader.read_exact(
        context.attempt.work.scope, accepted_output.reference
    )
    assert spec.c4_version == "1.0.0"
    assert len(spec.sections) == 6
    assert manifest.generation_id == candidate_id

    # Open verified PDF handle
    pdf_handle = reader.open_exact(
        context.attempt.work.scope, accepted_output.reference, member="pdf"
    )
    pdf_bytes = pdf_handle.read()
    pdf_handle.close()

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert hashlib.sha256(pdf_bytes).hexdigest() == gen_after.pdf_sha256
    assert len(pdf_bytes) == gen_after.pdf_size

    # 5. Replay idempotency: re-running handler on same attempt returns prior candidate
    replayed_output = handler.execute(context)
    assert replayed_output.candidate.generation_id == candidate_id


def test_report_pipeline_prerequisite_failure(test_db) -> None:
    context, diagrams = sample_work_context()
    limits = ReportLimits()

    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    renderer = ReportLabPdfRenderer()

    handler = ReportWorkHandler(
        binding=context.attempt.work.binding,
        engine_or_session=test_db,
        preparer=preparer,
        renderer=renderer,
        limits=limits,
    )

    # Mutate context to have no prerequisites
    invalid_context = context.model_copy(update={"prerequisites": None})
    with pytest.raises(DeliveryExecutionFailure) as exc_info:
        handler.execute(invalid_context)

    assert "report_prerequisites_missing" in exc_info.value.failure.code
