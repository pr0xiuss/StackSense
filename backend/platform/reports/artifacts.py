"""Report artifact storage, sealing, verified handles, and operator cleanup.

Implements the shared GeneratedArtifactStore Protocol for Literal["spec", "pdf"].
Producers stage and seal private candidate artifacts; consumers read only
accepted, pinned artifacts with SHA256 and length verification.
"""

from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
import shutil
import stat
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
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
READONLY = os.O_RDONLY | _O_CLOEXEC | _O_NOFOLLOW | os.O_NONBLOCK
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
            try:
                self._authority.recheck(self._scope, self._reference)
            finally:
                self._lease.close()


def _read_hash_file(
    path: Path, expected_size: int, expected_sha256: str, deadline: float
) -> bytes:
    if monotonic() >= deadline:
        raise TimeoutError("report_timeout")
    with ExitStack() as stack:
        parent = os.open(path.anchor, DIRECTORY)
        stack.callback(os.close, parent)
        for part in path.parent.parts[1:]:
            parent = os.open(part, DIRECTORY, dir_fd=parent)
            stack.callback(os.close, parent)
        fd = os.open(path.name, READONLY, dir_fd=parent)
        stack.callback(os.close, fd)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_size != expected_size
        ):
            raise ValueError("report_integrity_error")
        chunks: list[bytes] = []
        remaining = expected_size
        while remaining:
            if monotonic() >= deadline:
                raise TimeoutError("report_timeout")
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                raise ValueError("report_integrity_error")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise ValueError("report_integrity_error")
        data = b"".join(chunks)
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


@contextmanager
def generation_lock(root: Path, generation_id: UUID) -> Iterator[None]:
    """Serialize application writers/GC; this is not a physical-principal seal."""
    locks = root / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    if locks.is_symlink():
        raise ValueError("report_integrity_error")
    fd = os.open(
        locks / str(generation_id),
        os.O_RDWR | os.O_CREAT | _O_NOFOLLOW | _O_CLOEXEC,
        0o600,
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


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
        require_staging: Callable[[AttemptIdentity], None] | None = None,
    ) -> None:
        self.attempt = attempt
        self.candidate_id = candidate_id
        self.artifact_id = artifact_id
        self.limits = limits or ReportLimits()
        self.root = root or REPORT_STORE_ROOT
        self.require_staging = require_staging
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
        with generation_lock(self.root, self.candidate_id):
            if self.require_staging is None:
                raise PermissionError("report write requires staging authority")
            self.require_staging(self.attempt)
            return self._stage_artifacts(
                spec,
                pdf_bytes,
                pdf_sha256,
                page_count,
                source_snapshot_digest,
                renderer_profile_digest,
                limits_digest,
                page_placement_digest,
                asset_hashes,
            )

    def _stage_artifacts(
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
        spec = ReportSpec.model_validate(spec)
        if (
            spec.metadata.scope != self.attempt.work.scope
            or spec.metadata.profile != self.attempt.work.binding
            or source_snapshot_digest != spec.metadata.source_snapshot_digest
        ):
            raise ReportContractError("report_integrity_error")
        if self.sealed_dir.exists():
            raw = self.sealed_dir / "manifest.json"
            if raw.is_symlink() or raw.stat().st_size > self.limits.max_spec_bytes:
                raise ReportContractError("report_integrity_error")
            manifest = ReportArtifactManifest.from_bytes(
                raw.read_bytes(), max_bytes=self.limits.max_spec_bytes
            )
            if (
                manifest.attempt_id != self.attempt.attempt_id
                or manifest.generation_id != self.candidate_id
                or manifest.artifact_id != self.artifact_id
                or manifest.scope != self.attempt.work.scope
                or manifest.binding != self.attempt.work.binding
                or manifest.report_spec_digest != spec.report_spec_digest
            ):
                raise ReportContractError("report_integrity_error")
            for member in manifest.members:
                _read_hash_file(
                    self.sealed_dir / member.file_name,
                    member.size_bytes,
                    member.sha256,
                    monotonic() + self.limits.read_timeout_seconds,
                )
            pdf = next(m for m in manifest.members if m.member == "pdf")
            if pdf.sha256 != pdf_sha256 or pdf.size_bytes != len(pdf_bytes):
                raise ReportContractError("report_integrity_error")
            seal = CandidateSeal(
                generation_id=self.candidate_id,
                artifact_id=self.artifact_id,
                digests=OutputDigests(
                    content=hashlib.sha256(manifest.to_bytes()).hexdigest(),
                    spec=manifest.report_spec_digest,
                    layout=None,
                ),
                size_bytes=len(manifest.to_bytes()),
                sealed=True,
            )
            return manifest, seal, PreparedOutput(attempt=self.attempt, candidate=seal)
        if hashlib.sha256(pdf_bytes).hexdigest() != pdf_sha256:
            raise ReportContractError("report_integrity_error")
        if self.staging_dir.exists():
            if self.staging_dir.is_symlink() or set(
                p.name for p in self.staging_dir.iterdir()
            ) - {"report-spec.json", "report.pdf", "manifest.json"}:
                raise ReportContractError("report_integrity_error")
            for name in ("report-spec.json", "report.pdf", "manifest.json"):
                path = self.staging_dir / name
                if path.exists():
                    if path.is_symlink() or not path.is_file():
                        raise ReportContractError("report_integrity_error")
                    path.unlink()
        self.staging_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        def write(path: Path, data: bytes) -> None:
            fd = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC,
                0o600,
            )
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())

        # 1. Write spec
        spec_bytes = c4_canonical_bytes(spec.model_dump(mode="python"))
        spec_size = len(spec_bytes)
        spec_sha256 = hashlib.sha256(spec_bytes).hexdigest()
        spec_path = self.staging_dir / "report-spec.json"
        if (
            spec_size > self.limits.max_spec_bytes
            or spec_size + len(pdf_bytes) > self.limits.max_staged_bytes
        ):
            raise ReportContractError("report_limit_exceeded")
        write(spec_path, spec_bytes)

        # 2. Write PDF
        pdf_size = len(pdf_bytes)
        if pdf_size > self.limits.max_pdf_bytes:
            raise ReportContractError(
                f"PDF size {pdf_size} exceeds maximum {self.limits.max_pdf_bytes}"
            )
        pdf_path = self.staging_dir / "report.pdf"
        write(pdf_path, pdf_bytes)

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
        if (
            spec_size + len(pdf_bytes) + len(manifest_bytes)
            > self.limits.max_staged_bytes
        ):
            raise ReportContractError("report_limit_exceeded")
        write(manifest_path, manifest_bytes)
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        manifest_size = len(manifest_bytes)

        # Seal promote: move staging to sealed
        self.sealed_dir.parent.mkdir(parents=True, exist_ok=True)
        import ctypes

        rename = ctypes.CDLL(None, use_errno=True).renameat2
        if (
            rename(
                -100,
                os.fsencode(self.staging_dir),
                -100,
                os.fsencode(self.sealed_dir),
                1,
            )
            != 0
        ):
            raise OSError(ctypes.get_errno(), "report promotion failed")
        for directory in (
            self.sealed_dir,
            self.sealed_dir.parent,
            self.staging_dir.parent,
        ):
            fd = os.open(directory, DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

        # Check permissions and readback
        sealed_manifest_path = self.sealed_dir / "manifest.json"
        readback_manifest = sealed_manifest_path.read_bytes()
        if hashlib.sha256(readback_manifest).hexdigest() != manifest_sha256:
            raise ValueError("seal_verification_failed")
        for member in manifest.members:
            _read_hash_file(
                self.sealed_dir / member.file_name,
                member.size_bytes,
                member.sha256,
                monotonic() + self.limits.read_timeout_seconds,
            )

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

    def __init__(
        self,
        root: Path | None = None,
        require_deleting: Callable[[UUID], None] | None = None,
    ) -> None:
        self.root = root or REPORT_STORE_ROOT
        self.require_deleting = require_deleting

    def cleanup_unaccepted(
        self,
        candidate_id: UUID,
        grace_seconds: float = 300.0,
    ) -> bool:
        """Safely remove a candidate staging or unaccepted sealed directory."""
        if self.require_deleting is None:
            raise PermissionError("report cleanup requires reserved deletion authority")
        self.require_deleting(candidate_id)
        staging_dir = self.root / "staging" / str(candidate_id)
        if staging_dir.exists():
            if staging_dir.is_symlink():
                raise ValueError("report_integrity_error")
            shutil.rmtree(staging_dir)

        sealed_dir = self.root / "sealed" / str(candidate_id)
        if sealed_dir.exists():
            mtime = sealed_dir.stat().st_mtime
            if (datetime.now().timestamp() - mtime) >= grace_seconds:
                if sealed_dir.is_symlink():
                    raise ValueError("report_integrity_error")
                shutil.rmtree(sealed_dir)
                return True
            return False
        return True
