"""Tests for report artifact candidate staging, sealing, and verified handle access."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest

from backend.platform.delivery.contracts import ArtifactReference, VersionScope
from backend.platform.reports.artifacts import (
    CandidateReportWriter,
    LocalReportArtifactStore,
    ReportAcceptedReadAuthority,
    ReportOperatorGC,
)
from backend.platform.reports.contracts import ReportArtifactManifest
from backend.platform.reports.model import c4_report_resource_id
from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.preparation import ReportPreparer
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


class FakeReadAuthority(ReportAcceptedReadAuthority):
    def __init__(self, manifest: ReportArtifactManifest) -> None:
        self.manifest = manifest

    @contextmanager
    def pinned(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> Iterator[ReportArtifactManifest]:
        yield self.manifest

    def recheck(self, scope: VersionScope, reference: ArtifactReference) -> None:
        pass


def test_candidate_writer_and_store_roundtrip(tmp_path: Path) -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared = preparer.prepare(context)
    renderer = ReportLabPdfRenderer()
    rendered = renderer.render(prepared, deadline=time.monotonic() + 30.0)

    candidate_id = uuid4()
    artifact_id = uuid4()
    writer = CandidateReportWriter(
        attempt=context.attempt,
        candidate_id=candidate_id,
        artifact_id=artifact_id,
        root=tmp_path,
        require_staging=lambda attempt: None,
    )

    manifest, seal, prepared_output = writer.stage_artifacts(
        spec=spec,
        pdf_bytes=rendered.pdf_bytes,
        pdf_sha256=rendered.sha256,
        page_count=rendered.page_count,
        source_snapshot_digest=spec.metadata.source_snapshot_digest,
        renderer_profile_digest="1" * 64,
        limits_digest="2" * 64,
        page_placement_digest="3" * 64,
    )

    assert manifest.generation_id == candidate_id
    assert manifest.artifact_id == artifact_id
    assert seal.size_bytes > 0
    assert seal.digests.content == hashlib.sha256(manifest.to_bytes()).hexdigest()

    rid = c4_report_resource_id(
        context.attempt.work.scope,
        context.attempt.work.binding,
        context.attempt.work.input_fingerprint,
    )
    # Now verify store reads both members
    ref = ArtifactReference(
        scope=context.attempt.work.scope,
        binding=context.attempt.work.binding,
        generation_id=candidate_id,
        artifact_id=artifact_id,
        candidate_id=candidate_id,
        resource_id=rid,
        input_fingerprint=context.attempt.work.input_fingerprint,
        sealed=True,
        digests=seal.digests,
        size_bytes=seal.size_bytes,
    )

    authority = FakeReadAuthority(manifest)
    store = LocalReportArtifactStore(authority=authority, root=tmp_path)

    # 1. Read spec member
    spec_handle = store.open_exact(context.attempt.work.scope, ref, "spec")
    spec_bytes = spec_handle.read()
    spec_handle.close()
    assert len(spec_bytes) > 0
    assert b"c4_version" in spec_bytes

    # 2. Read pdf member
    pdf_handle = store.open_exact(context.attempt.work.scope, ref, "pdf")
    pdf_bytes = pdf_handle.read()
    pdf_handle.close()
    assert pdf_bytes == rendered.pdf_bytes


def test_store_rejects_corrupted_manifest(tmp_path: Path) -> None:
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        architecture_query=FakeArchitectureQueryService(),
        analysis_lifecycle=FakeAnalysisLifecycleService(),
        diagram_reader=FakeDiagramReader(diagrams),
    )
    spec, snapshot, prepared = preparer.prepare(context)
    renderer = ReportLabPdfRenderer()
    rendered = renderer.render(prepared, deadline=time.monotonic() + 30.0)

    candidate_id = uuid4()
    artifact_id = uuid4()
    writer = CandidateReportWriter(
        attempt=context.attempt,
        candidate_id=candidate_id,
        artifact_id=artifact_id,
        root=tmp_path,
        require_staging=lambda attempt: None,
    )
    manifest, seal, _ = writer.stage_artifacts(
        spec=spec,
        pdf_bytes=rendered.pdf_bytes,
        pdf_sha256=rendered.sha256,
        page_count=rendered.page_count,
        source_snapshot_digest=spec.metadata.source_snapshot_digest,
        renderer_profile_digest="1" * 64,
        limits_digest="2" * 64,
        page_placement_digest="3" * 64,
    )

    # Corrupt manifest file on disk
    manifest_file = tmp_path / "sealed" / str(candidate_id) / "manifest.json"
    manifest_file.write_bytes(b"corrupt payload")

    rid = c4_report_resource_id(
        context.attempt.work.scope,
        context.attempt.work.binding,
        context.attempt.work.input_fingerprint,
    )
    ref = ArtifactReference(
        scope=context.attempt.work.scope,
        binding=context.attempt.work.binding,
        generation_id=candidate_id,
        artifact_id=artifact_id,
        candidate_id=candidate_id,
        resource_id=rid,
        input_fingerprint=context.attempt.work.input_fingerprint,
        sealed=True,
        digests=seal.digests,
        size_bytes=seal.size_bytes,
    )
    authority = FakeReadAuthority(manifest)
    store = LocalReportArtifactStore(authority=authority, root=tmp_path)

    with pytest.raises(ValueError):
        store.open_exact(context.attempt.work.scope, ref, "pdf")


def test_operator_gc_removes_unaccepted(tmp_path: Path) -> None:
    candidate_id = uuid4()
    staging_dir = tmp_path / "staging" / str(candidate_id)
    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "temp.txt").write_bytes(b"temp")

    gc = ReportOperatorGC(root=tmp_path, require_deleting=lambda candidate: None)
    gc.cleanup_unaccepted(candidate_id, grace_seconds=0.0)
    assert not staging_dir.exists()
