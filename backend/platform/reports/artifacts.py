"""Report artifact storage, sealing, verified handles, and operator cleanup.

Implements the shared GeneratedArtifactStore Protocol for Literal["spec", "pdf"].
Producers stage and seal private candidate artifacts; consumers read only
accepted, pinned artifacts with SHA256 and length verification.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
from contextlib import AbstractContextManager, ExitStack
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Literal, Protocol
from uuid import UUID, uuid5

from backend.platform.delivery.artifacts import (
    GeneratedArtifactStore,
    VerifiedArtifactHandle,
)
from backend.platform.delivery.contracts import (
    ArtifactReference,
    AttemptIdentity,
    CandidateSeal,
    OutputDigests,
    PreparedOutput,
    VersionScope,
)
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import (
    ReportArtifactDescriptor,
    ReportArtifactManifest,
    ReportArtifactMember,
    ReportContractError,
    ReportSpec,
)
from backend.platform.reports.model import (
    c4_canonical_bytes,
    c4_render_fingerprint,
    c4_report_resource_id,
    c4_report_spec_digest,
)

REPORT_STORE_ROOT = Path("/var/lib/stacksense/reports")

_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
READONLY = os.O_RDONLY | _O_CLOEXEC | _O_NOFOLLOW
DIRECTORY = READONLY | _O_DIRECTORY


class ReportAcceptedReadAuthority(Protocol):
    """Authority acquiring pins before reading accepted report artifacts."""

    def pinned(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> AbstractContextManager[ReportArtifactManifest]: ...

    def recheck(self, scope: VersionScope, reference: ArtifactReference) -> None: ...

    def descriptor(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> ReportArtifactDescriptor: ...


class _VerifiedReportHandle(VerifiedArtifactHandle):
    """Handle wrapping verified bytes of a report artifact member."""

    def __init__(
        self,
        data: bytes,
        lease: ExitStack,
        authority: ReportAcceptedReadAuthority,
        scope: VersionScope,
        reference: ArtifactReference,
        deadline: float,
    ) -> None:
        self._stream = io.BytesIO(data)
        self._lease = lease
        self._authority = authority
        self._scope = scope
        self._reference = reference
        self._deadline = deadline
        self._closed = False

    def read(self, size: int = -1) -> bytes:
        if self._closed:
            raise ValueError("handle is closed")
        if monotonic() >= self._deadline:
            raise TimeoutError("report_stream_timeout")
        return self._stream.read(size)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._stream.close()
            self._lease.close()


def _read_hash_file(
    path: Path, expected_size: int, expected_sha256: str, deadline: float
) -> bytes:
    if monotonic() >= deadline:
        raise TimeoutError("report_timeout")
    if not path.is_file() or path.is_symlink():
        raise ValueError("report_integrity_error")
    data = path.read_bytes()
    if len(data) != expected_size:
        raise ValueError(
            f"report_size_mismatch: expected {expected_size}, got {len(data)}"
        )
    actual_hash = hashlib.sha256(data).hexdigest()
    if actual_hash != expected_sha256:
        raise ValueError(
            f"report_hash_mismatch: expected {expected_sha256}, got {actual_hash}"
        )
    return data


class LocalReportArtifactStore(GeneratedArtifactStore[Literal["spec", "pdf"]]):
    """Filesystem-backed store implementing GeneratedArtifactStore for reports."""

    def __init__(
        self,
        authority: ReportAcceptedReadAuthority,
        limits: ReportLimits | None = None,
        root: Path | None = None,
    ) -> None:
        self.authority = authority
        self.limits = limits or ReportLimits()
        self.root = root or REPORT_STORE_ROOT

    def open_exact(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        member: Literal["spec", "pdf"],
    ) -> VerifiedArtifactHandle:
        read_deadline = monotonic() + self.limits.read_timeout_seconds
        if isinstance(scope, dict):
            scope = VersionScope.model_validate_json(json.dumps(scope))
        elif not isinstance(scope, VersionScope):
            scope = VersionScope.model_validate(scope)

        if isinstance(reference, dict):
            reference = ArtifactReference.model_validate_json(json.dumps(reference))
        elif not isinstance(reference, ArtifactReference):
            reference = ArtifactReference.model_validate(reference)

        if scope != reference.scope or member not in ("spec", "pdf"):
            raise ValueError("report_scope_mismatch")
        if reference.size_bytes > self.limits.max_spec_bytes:
            raise ValueError("report_limit_exceeded")

        lease = ExitStack()
        try:
            expected = lease.enter_context(self.authority.pinned(scope, reference))
            gen_dir = self.root / "sealed" / str(reference.generation_id)
            if not gen_dir.exists() or not gen_dir.is_dir():
                raise FileNotFoundError("report_generation_unavailable")

            manifest_path = gen_dir / "manifest.json"
            manifest_bytes = _read_hash_file(
                manifest_path,
                reference.size_bytes,
                reference.digests.content,
                read_deadline,
            )
            manifest = ReportArtifactManifest.from_bytes(
                manifest_bytes, max_bytes=self.limits.max_spec_bytes
            )
            if manifest != expected:
                raise ValueError("report_integrity_error")

            member_desc = next(m for m in manifest.members if m.member == member)
            file_path = gen_dir / member_desc.file_name
            member_bytes = _read_hash_file(
                file_path,
                member_desc.size_bytes,
                member_desc.sha256,
                read_deadline,
            )

            self.authority.recheck(scope, reference)
            if monotonic() >= read_deadline:
                raise TimeoutError("report_timeout")

            return _VerifiedReportHandle(
                member_bytes,
                lease.pop_all(),
                self.authority,
                scope,
                reference,
                monotonic() + 30.0,
            )
        finally:
            lease.close()


class CandidateReportWriter:
    """Manages isolated staging, hashing, and sealing of report artifact candidates."""

    def __init__(
        self,
        attempt: AttemptIdentity,
        candidate_id: UUID,
        artifact_id: UUID,
        limits: ReportLimits | None = None,
        root: Path | None = None,
    ) -> None:
        self.attempt = attempt
        self.candidate_id = candidate_id
        self.artifact_id = artifact_id
        self.limits = limits or ReportLimits()
        self.root = root or REPORT_STORE_ROOT
        self.staging_dir = self.root / "staging" / str(candidate_id)
        self.sealed_dir = self.root / "sealed" / str(candidate_id)

    def stage_artifacts(
        self,
        spec: ReportSpec,
        pdf_bytes: bytes,
        pdf_sha256: str,
        page_count: int,
        source_snapshot_digest: str,
        renderer_profile_digest: str,
        limits_digest: str,
        page_placement_digest: str,
        asset_hashes: tuple[tuple[str, str], ...] = (),
    ) -> tuple[ReportArtifactManifest, CandidateSeal, PreparedOutput]:
        """Stage spec and PDF bytes, write manifest, and compute seal."""
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write spec
        spec_bytes = c4_canonical_bytes(spec.model_dump(mode="python"))
        spec_size = len(spec_bytes)
        spec_sha256 = hashlib.sha256(spec_bytes).hexdigest()
        spec_path = self.staging_dir / "report-spec.json"
        spec_path.write_bytes(spec_bytes)

        # 2. Write PDF
        pdf_size = len(pdf_bytes)
        if pdf_size > self.limits.max_pdf_bytes:
            raise ReportContractError(
                f"PDF size {pdf_size} exceeds maximum {self.limits.max_pdf_bytes}"
            )
        pdf_path = self.staging_dir / "report.pdf"
        pdf_path.write_bytes(pdf_bytes)

        # Calculate digests
        spec_digest = c4_report_spec_digest(spec)
        render_fp = c4_render_fingerprint(
            report_spec_digest=spec_digest,
            renderer_profile_digest=renderer_profile_digest,
            asset_hashes=asset_hashes,
            limits_digest=limits_digest,
            page_placement_digest=page_placement_digest,
        )

        members = (
            ReportArtifactMember(
                member="spec",
                file_name="report-spec.json",
                media_type="application/json",
                size_bytes=spec_size,
                sha256=spec_sha256,
            ),
            ReportArtifactMember(
                member="pdf",
                file_name="report.pdf",
                media_type="application/pdf",
                size_bytes=pdf_size,
                sha256=pdf_sha256,
            ),
        )

        diagram_receipt_ids = tuple(d.receipt.receipt_id for d in spec.diagram_inputs)
        diagram_digests = tuple(
            d.receipt.accepted.reference.digests.content for d in spec.diagram_inputs
        )
        rid = c4_report_resource_id(
            self.attempt.work.scope,
            self.attempt.work.binding,
            self.attempt.work.input_fingerprint,
        )
        run_uuid = uuid5(self.attempt.attempt_id, f"run:{self.attempt.work.run_number}")

        manifest = ReportArtifactManifest(
            artifact_schema_version="1.0.0",
            scope=self.attempt.work.scope,
            binding=self.attempt.work.binding,
            input_fingerprint=self.attempt.work.input_fingerprint,
            attempt_id=self.attempt.attempt_id,
            work_id=self.attempt.work.work_id,
            run_id=run_uuid,
            candidate_id=self.candidate_id,
            fence_token=self.attempt.fence,
            epoch=self.attempt.dispatch_epoch,
            resource_id=rid,
            generation_id=self.candidate_id,
            artifact_id=self.artifact_id,
            source_snapshot_digest=source_snapshot_digest,
            report_spec_digest=spec_digest,
            render_fingerprint=render_fp,
            page_placement_digest=page_placement_digest,
            diagram_receipt_ids=diagram_receipt_ids,
            diagram_member_digests=diagram_digests,
            page_count=page_count,
            members=members,
        )

        manifest_bytes = manifest.to_bytes()
        manifest_path = self.staging_dir / "manifest.json"
        manifest_path.write_bytes(manifest_bytes)
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        manifest_size = len(manifest_bytes)

        # Seal promote: move staging to sealed
        if self.sealed_dir.exists():
            shutil.rmtree(self.sealed_dir)
        self.sealed_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.staging_dir), str(self.sealed_dir))

        # Check permissions and readback
        sealed_manifest_path = self.sealed_dir / "manifest.json"
        readback_manifest = sealed_manifest_path.read_bytes()
        if hashlib.sha256(readback_manifest).hexdigest() != manifest_sha256:
            raise ValueError("seal_verification_failed")

        seal = CandidateSeal(
            generation_id=self.candidate_id,
            artifact_id=self.artifact_id,
            digests=OutputDigests(
                content=manifest_sha256,
                spec=spec_digest,
                layout=None,
            ),
            size_bytes=manifest_size,
            sealed=True,
        )

        prepared = PreparedOutput(attempt=self.attempt, candidate=seal)
        return manifest, seal, prepared


class ReportOperatorGC:
    """Bounded operator orphan candidate cleaner for report directories."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or REPORT_STORE_ROOT

    def cleanup_unaccepted(
        self,
        candidate_id: UUID,
        grace_seconds: float = 300.0,
    ) -> bool:
        """Safely remove a candidate staging or unaccepted sealed directory."""
        staging_dir = self.root / "staging" / str(candidate_id)
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

        sealed_dir = self.root / "sealed" / str(candidate_id)
        if sealed_dir.exists():
            mtime = sealed_dir.stat().st_mtime
            if (datetime.now().timestamp() - mtime) >= grace_seconds:
                shutil.rmtree(sealed_dir, ignore_errors=True)
                return True
        return False
