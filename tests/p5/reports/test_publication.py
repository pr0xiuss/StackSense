"""Tests for ReportRepository and ReportPublicationPort acceptance semantics."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.delivery.publication import (
    GuardedEnlistedSession,
    PublicationContext,
    PublicationGuard,
)
from backend.platform.reports.artifacts import CandidateReportWriter
from backend.platform.reports.model import (
    c4_report_resource_id,
)
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
    ReportPublicationPort,
    ReportRepository,
)
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    for table in REPORT_TABLES:
        table.create(engine, checkfirst=True)
    yield engine
    engine.dispose()


def test_report_repository_resource_and_snapshot_cas(memory_db) -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared = preparer.prepare(context)

    with Session(memory_db) as session:
        repo = ReportRepository(session)
        scope = context.attempt.work.scope
        binding = context.attempt.work.binding
        input_fp = context.attempt.work.input_fingerprint

        # 1. get_or_create_resource
        res = repo.get_or_create_resource(scope, binding, input_fp)
        session.commit()
        expected_rid = c4_report_resource_id(scope, binding, input_fp)
        assert res.id == expected_rid
        assert res.captured_snapshot is None

        # 2. capture_snapshot
        res2 = repo.capture_snapshot(res.id, snapshot)
        session.commit()
        assert res2.captured_snapshot is not None
        assert res2.source_snapshot_digest == snapshot.snapshot_digest

        # 3. capture_snapshot second time is idempotent
        res3 = repo.capture_snapshot(res.id, snapshot)
        assert res3.source_snapshot_digest == snapshot.snapshot_digest


def test_report_repository_candidate_lifecycle_and_publication(
    memory_db, tmp_path
) -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared = preparer.prepare(context)

    candidate_id = context.attempt.candidate_id
    artifact_id = uuid4()

    with Session(memory_db) as session:
        repo = ReportRepository(session)
        gen = repo.allocate_candidate(context.attempt, candidate_id, artifact_id)
        session.commit()
        assert gen.state == "STAGING"
        assert gen.id == candidate_id

    # Stage artifacts on disk to get manifest & seal
    writer = CandidateReportWriter(
        attempt=context.attempt,
        candidate_id=candidate_id,
        artifact_id=artifact_id,
        root=tmp_path,
    )
    manifest, seal, prepared_output = writer.stage_artifacts(
        spec=spec,
        pdf_bytes=b"%PDF-1.4 dummy",
        pdf_sha256=hashlib.sha256(b"%PDF-1.4 dummy").hexdigest(),
        page_count=5,
        source_snapshot_digest="0" * 64,
        renderer_profile_digest="1" * 64,
        limits_digest="2" * 64,
        page_placement_digest="3" * 64,
    )

    seal_proof = {
        "verification_version": "1.0.0",
        "manifest_sha256": seal.digests.content,
        "pdf_sha256": hashlib.sha256(b"%PDF-1.4 dummy").hexdigest(),
        "sealed_at": datetime.now(UTC).isoformat(),
    }

    with Session(memory_db) as session:
        repo = ReportRepository(session)
        gen = repo.record_sealed(
            generation_id=candidate_id,
            manifest=manifest,
            seal_proof=seal_proof,
            pdf_bytes=b"%PDF-1.4 dummy",
            pdf_sha256=seal_proof["pdf_sha256"],
            page_count=5,
        )
        session.commit()
        assert gen.state == "SEALED_VERIFIED"
        assert gen.manifest_size == seal.size_bytes

    # Now test publication port
    with Session(memory_db) as session:
        # Wrap session in GuardedEnlistedSession
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

        # Check generation is now ACCEPTED
        gen_after = session.get(Generation, candidate_id)
        assert gen_after.state == "ACCEPTED"
        assert gen_after.accepted_at is not None

        # Check resource points to active generation
        rid = c4_report_resource_id(
            context.attempt.work.scope,
            context.attempt.work.binding,
            context.attempt.work.input_fingerprint,
        )
        res_after = session.get(Resource, rid)
        assert res_after.accepted_generation_id == candidate_id

        # Validate ready succeeds
        ready = pub_port.validate_ready(accepted_output.reference, pub_ctx)
        assert ready.reference == accepted_output.reference
