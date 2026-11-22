"""Consumer-shaped fixtures and compatibility tests for C4 v1.0.0 and M6 consumers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.platform.delivery.contracts import ArtifactReference, OutputDigests
from backend.platform.reports.contracts import (
    REPORT_TYPE,
    ReportArtifactDescriptor,
    ReportArtifactManifest,
    ReportArtifactMember,
    ReportCollection,
    ReportGenerationPage,
    ReportGenerationSummary,
    ReportSlotStatus,
    ReportSummary,
)
from backend.platform.reports.model import c4_canonical_bytes
from tests.p5.reports.conftest import sample_handler_profile, sample_scope


def test_report_artifact_manifest_and_descriptor_schema() -> None:
    scope = sample_scope()
    binding = sample_handler_profile()
    gen_id = uuid4()
    art_id = uuid4()
    members = (
        ReportArtifactMember(
            member="spec",
            file_name="report-spec.json",
            media_type="application/json",
            size_bytes=1024,
            sha256="1" * 64,
        ),
        ReportArtifactMember(
            member="pdf",
            file_name="report.pdf",
            media_type="application/pdf",
            size_bytes=20480,
            sha256="2" * 64,
        ),
    )
    manifest = ReportArtifactManifest(
        artifact_schema_version="1.0.0",
        scope=scope,
        binding=binding,
        input_fingerprint="a" * 64,
        attempt_id=uuid4(),
        work_id=uuid4(),
        run_id=uuid4(),
        candidate_id=uuid4(),
        fence_token=1,
        epoch=uuid4(),
        resource_id=uuid4(),
        generation_id=gen_id,
        artifact_id=art_id,
        source_snapshot_digest="3" * 64,
        report_spec_digest="4" * 64,
        render_fingerprint="5" * 64,
        diagram_receipt_ids=(uuid4(), uuid4(), uuid4(), uuid4()),
        diagram_member_digests=("6" * 64, "7" * 64, "8" * 64, "9" * 64),
        page_placement_digest="b" * 64,
        page_count=6,
        members=members,
    )

    manifest_bytes = manifest.to_bytes()
    assert len(manifest_bytes) > 0

    ref = ArtifactReference(
        scope=scope,
        binding=binding,
        input_fingerprint=manifest.input_fingerprint,
        resource_id=manifest.resource_id,
        candidate_id=manifest.candidate_id,
        generation_id=gen_id,
        artifact_id=art_id,
        size_bytes=len(manifest_bytes),
        sealed=True,
        digests=OutputDigests(
            content=manifest.members[1].sha256,
            spec=manifest.report_spec_digest,
            layout=None,
        ),
    )
    descriptor = ReportArtifactDescriptor(
        reference=ref,
        manifest=manifest,
    )
    assert descriptor.reference == ref
    assert descriptor.manifest == manifest


def test_report_summary_and_collection_for_m6() -> None:
    scope = sample_scope()
    binding = sample_handler_profile()
    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)

    summary = ReportSummary(
        scope=scope,
        report_id=UUID("00000000-0000-0000-0000-000000000010"),
        report_type=REPORT_TYPE,
        profile=binding,
        input_fingerprint="a" * 64,
        availability="ready",
        readability="readable",
        pdf_size_bytes=20480,
        pdf_sha256="c" * 64,
        page_count=6,
        spec_digest="d" * 64,
        created_at=now,
        accepted_at=now,
        observed_at=now,
    )

    collection = ReportCollection(
        scope=scope,
        automatic=ReportSlotStatus(
            status="ready",
            waiting_on=(),
        ),
        items=(summary,),
        next_cursor=None,
    )
    json_bytes = c4_canonical_bytes(collection)
    assert len(json_bytes) > 0
    assert summary.availability == "ready"
    assert len(collection.items) == 1


def test_report_generation_page_for_m6() -> None:
    scope = sample_scope()
    binding = sample_handler_profile()
    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)

    ref = ArtifactReference(
        scope=scope,
        binding=binding,
        input_fingerprint="a" * 64,
        resource_id=uuid4(),
        candidate_id=uuid4(),
        generation_id=uuid4(),
        artifact_id=uuid4(),
        size_bytes=1000,
        sealed=True,
        digests=OutputDigests(content="e" * 64),
    )

    gen_summary = ReportGenerationSummary(
        generation_id=ref.generation_id,
        artifact_id=ref.artifact_id,
        accepted_at=now,
        page_count=6,
        pdf_size_bytes=20480,
        pdf_sha256="f" * 64,
        report_spec_digest="0" * 64,
        reference=ref,
    )

    page = ReportGenerationPage(
        scope=scope,
        report_id=ref.resource_id,
        items=(gen_summary,),
        next_cursor="signed_cursor_token_v1",
    )
    assert page.next_cursor == "signed_cursor_token_v1"
    assert len(page.items) == 1
