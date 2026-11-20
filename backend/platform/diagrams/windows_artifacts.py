"""Separate-identity NTFS sealing prototype. Not registered for production.

The caller must already run as the dedicated sealer identity. This adapter
never receives a password, impersonates the worker, or changes machine ACLs.
Actual Windows ACL/handle/race proofs are mandatory before deployment.
"""

from __future__ import annotations

import ctypes as c
import hashlib
import re
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from backend.platform.diagrams.artifact_contracts import SealProof, SealRequest
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import DiagramArtifactManifest
from backend.platform.diagrams.model import canonical_bytes
from backend.platform.diagrams.windows_native import PTR, U32, NativeWindows

ROOT = Path(r"C:\ProgramData\StackSense\Diagrams")


class StagingAuthority(Protocol):
    def require_staging(self, request: SealRequest) -> None: ...
    def require_deleting(self, generation_id: UUID) -> None: ...


def sealer_sddl(owner: str, reader: str) -> str:
    for sid in (owner, reader):
        if re.fullmatch(r"S-1-5-(?:[0-9]+-)*[0-9]+", sid) is None:
            raise ValueError("diagram_store_unavailable")
    if owner == reader or owner in ("S-1-5-18", "S-1-5-32-544"):
        raise ValueError("diagram_store_unavailable")
    return f"O:{owner}D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;{owner})(A;;GRGX;;;{reader})"


class WindowsPrincipalSealer:
    def __init__(
        self,
        metadata: StagingAuthority,
        limits: DiagramLimits,
        *,
        sealer_sid: str,
        worker_sid: str,
        reader_sid: str,
    ) -> None:
        self.sddl = sealer_sddl(sealer_sid, reader_sid)
        if worker_sid == sealer_sid:
            raise ValueError("diagram_store_unavailable")
        self.native = NativeWindows()
        self.native.require_unprivileged()
        if self.native.token_sid() != sealer_sid:
            raise ValueError("diagram_store_unavailable")
        self.metadata, self.limits = metadata, limits
        self.owner, self.reader = sealer_sid, reader_sid

    def _lock(self, stack: ExitStack, generation_id: UUID) -> None:
        native = self.native
        for path in (ROOT, ROOT / "sealed", ROOT / "locks"):
            handle = stack.enter_context(native.file(path, directory=True))
            native.require_ntfs(handle)
            native.require_acl(handle, self.owner, self.reader)
        descriptor = stack.enter_context(native.descriptor(self.sddl))
        handle = native.api(
            native.kernel,
            "CreateFileW",
            [c.c_wchar_p, U32, U32, PTR, U32, U32, PTR],
            PTR,
        )(
            str(ROOT / "locks" / (str(generation_id) + ".lock")),
            0xC0020000,
            0,
            c.byref(descriptor),
            4,
            0x00200000,
            None,
        )
        if handle == PTR(-1).value:
            native.check(False)
        stack.callback(native.close, handle)
        info = native.information(handle)
        if info.attributes & 0x400 or info.links != 1:
            raise ValueError("diagram_integrity_error")
        native.require_acl(handle, self.owner, self.reader)

    def seal(self, request: SealRequest) -> SealProof:
        request = SealRequest.model_validate(request)
        limits = self.limits
        caps = {
            "spec": limits.max_spec_bytes,
            "layout": limits.max_layout_bytes,
            "members": limits.max_members_bytes,
            "svg": limits.max_svg_bytes,
        }
        if (
            request.manifest_size > limits.max_manifest_bytes
            or any(m.size_bytes > caps[m.member] for m in request.members)
            or sum(m.size_bytes for m in request.members)
            > limits.max_total_member_bytes
        ):
            raise ValueError("diagram_limit_exceeded")
        entries = (
            ("manifest.json", request.manifest_size, request.manifest_sha256),
            *((m.file_name, m.size_bytes, m.sha256) for m in request.members),
        )
        native = self.native
        with ExitStack() as stack:
            # Pin protected parents without delete sharing. Reparse/junction
            # parents cannot be swapped while any member path is resolved.
            self._lock(stack, request.generation_id)
            descriptor = stack.enter_context(native.descriptor(self.sddl))
            self.metadata.require_staging(request)
            final = ROOT / "sealed" / str(request.generation_id)
            if final.exists():
                self._verify(final, request, entries)
                return self._proof(final, request)
            source = ROOT / "staging" / str(request.generation_id)
            stack.enter_context(native.file(ROOT / "staging", directory=True))
            stack.enter_context(native.file(source, directory=True))
            if {x.name for x in source.iterdir()} != {entry[0] for entry in entries}:
                raise ValueError("diagram_integrity_error")
            candidate = ROOT / "sealed" / (".candidate-" + str(uuid4()))
            native.check(
                native.api(native.kernel, "CreateDirectoryW", [c.c_wchar_p, PTR])(
                    str(candidate), c.byref(descriptor)
                )
            )
            with native.file(candidate, directory=True) as target:
                native.require_acl(target, self.owner, self.reader)
            for name, size, digest in entries:
                with native.file(source / name) as incoming:
                    data = native.read(incoming, size)
                    if hashlib.sha256(data).hexdigest() != digest:
                        raise ValueError("diagram_integrity_error")
                with native.file(
                    candidate / name, write=True, new=True, security=descriptor
                ) as outgoing:
                    native.require_acl(outgoing, self.owner, self.reader)
                    native.write(outgoing, data)
            self._verify(candidate, request, entries)
            self.metadata.require_staging(request)
            # No replace-existing flag; same-volume NTFS placement only. The
            # protected parent and exclusive generation lock remain held.
            native.check(
                native.api(
                    native.kernel, "MoveFileExW", [c.c_wchar_p, c.c_wchar_p, U32]
                )(str(candidate), str(final), 8)
            )
            self._verify(final, request, entries)
            return self._proof(final, request)

    def delete_reserved(self, generation_id: UUID) -> None:
        generation_id = UUID(str(generation_id))
        native = self.native
        with ExitStack() as stack:
            self._lock(stack, generation_id)
            self.metadata.require_deleting(generation_id)
            directory = ROOT / "sealed" / str(generation_id)
            names = {
                "manifest.json",
                "spec.json",
                "layout.json",
                "members.json",
                "scene.svg",
            }
            with native.file(directory, directory=True) as parent:
                native.require_acl(parent, self.owner, self.reader)
                if {x.name for x in directory.iterdir()} != names:
                    raise ValueError("diagram_integrity_error")
                for name in names:
                    with native.file(directory / name) as handle:
                        native.require_acl(handle, self.owner, self.reader)
                self.metadata.require_deleting(generation_id)
                for name in sorted(names):
                    native.check(
                        native.api(native.kernel, "DeleteFileW", [c.c_wchar_p])(
                            str(directory / name)
                        )
                    )
            native.check(
                native.api(native.kernel, "RemoveDirectoryW", [c.c_wchar_p])(
                    str(directory)
                )
            )

    def _verify(
        self,
        path: Path,
        request: SealRequest,
        entries: tuple[tuple[str, int, str], ...],
    ) -> None:
        native = self.native
        with native.file(path, directory=True) as directory:
            native.require_acl(directory, self.owner, self.reader)
            if {x.name for x in path.iterdir()} != {x[0] for x in entries}:
                raise ValueError("diagram_integrity_error")
        for name, size, digest in entries:
            with native.file(path / name) as handle:
                native.require_acl(handle, self.owner, self.reader)
                data = native.read(handle, size)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError("diagram_integrity_error")
                if name == "manifest.json":
                    manifest = DiagramArtifactManifest.from_bytes(
                        data, max_bytes=self.limits.max_manifest_bytes
                    )
                    work = request.attempt.work
                    if (
                        manifest.to_bytes() != data
                        or manifest.scope != work.scope
                        or manifest.binding != work.binding
                        or manifest.input_fingerprint != work.input_fingerprint
                        or manifest.artifact_id != request.artifact_id
                        or manifest.generation_id != request.generation_id
                        or manifest.members != request.members
                    ):
                        raise ValueError("diagram_integrity_error")

    def _proof(self, path: Path, request: SealRequest) -> SealProof:
        with self.native.file(path, directory=True) as handle:
            info = self.native.information(handle)
            physical = f"{info.volume}:{info.index_high}:{info.index_low}"
        return SealProof(
            verification_version="1.0.0",
            manifest_sha256=request.manifest_sha256,
            member_set_digest=hashlib.sha256(
                canonical_bytes(request.members)
            ).hexdigest(),
            physical_object_id=physical,
            sealed_at=datetime.now(UTC),
        )
