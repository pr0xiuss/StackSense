"""Separate-principal fresh-inode sealing prototype; no same-UID fallback.

The fixed privileged entry chooses metadata validators, roots and principals.
Workers cannot provide paths, SQL, cleanup authority or arbitrary callbacks.
"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import os
import pwd
import selectors
import signal
import stat
import subprocess
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Literal, Protocol
from uuid import UUID, uuid4

from backend.platform.delivery.artifacts import (
    GeneratedArtifactStore as SharedGeneratedArtifactStore,
)
from backend.platform.delivery.contracts import (
    ArtifactReference,
    VersionScope,
)
from backend.platform.diagrams.artifact_contracts import SealProof as SealProof
from backend.platform.diagrams.artifact_contracts import SealRequest as SealRequest
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    DiagramArtifactDescriptor,
    DiagramArtifactManifest,
    VerifiedMemberHandle,
)
from backend.platform.diagrams.model import canonical_bytes, load_json

STORE_ROOT = Path("/var/lib/stacksense/diagrams")
READONLY = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
DIRECTORY = READONLY | os.O_DIRECTORY


def _proof_checkpoint(checkpoint: str, generation: UUID) -> None:
    """Admin-installed B1-only crash matrix. No worker argument/env control.

    Missing proof marker is the normal production path. B3 must remove proof
    configuration before capability registration; this never changes C0 state.
    """
    root = Path("/opt/stacksense/diagram-artifacts/deployment")
    marker = root / "proof-enabled"
    if not marker.exists():
        return
    for path in (root, *root.parents, marker, root / "seal-fault-cases.json"):
        info = path.lstat()
        if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("diagram_store_unavailable")
    if marker.stat().st_size != 19 or marker.read_bytes() != b"B1-ISOLATED-PROOFS\n":
        raise ValueError("diagram_store_unavailable")
    with (root / "seal-fault-cases.json").open("rb") as stream:
        data = stream.read(8193)
    if len(data) > 8192:
        raise ValueError("diagram_store_unavailable")
    value = load_json(data, max_bytes=8192)
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "cases"}
        or value["version"] != "1.0.0"
    ):
        raise ValueError("diagram_store_unavailable")
    if not isinstance(value["cases"], list) or len(value["cases"]) != 9:
        raise ValueError("diagram_store_unavailable")
    for case in value["cases"]:
        if not isinstance(case, dict) or set(case) != {"checkpoint", "generation_id"}:
            raise ValueError("diagram_store_unavailable")
        if (
            case["generation_id"] == str(generation)
            and case["checkpoint"] == checkpoint
        ):
            os.kill(os.getpid(), signal.SIGKILL)


class SealerMetadata(Protocol):
    def require_staging(self, request: SealRequest) -> None: ...

    def require_deleting(self, generation_id: UUID) -> None: ...


class GeneratedArtifactStore(
    SharedGeneratedArtifactStore[Literal["spec", "layout", "members", "svg"]],
    Protocol,
):
    """Future consumers receive accepted bytes, never an arbitrary path API."""

    authority: AcceptedReadAuthority

    def open_exact(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        member: Literal["spec", "layout", "members", "svg"],
    ) -> VerifiedMemberHandle: ...


class AcceptedReadAuthority(Protocol):
    """M4 metadata adapter must acquire a durable pin before granting this lease.

    No default/fake implementation is registered. B3 owns its SQL composition;
    a supplied descriptor or worker-generated seal is never read authorization.
    """

    def pinned(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> AbstractContextManager[DiagramArtifactManifest]: ...

    def recheck(self, scope: VersionScope, reference: ArtifactReference) -> None: ...


class LocalGeneratedArtifactStore:
    def __init__(self, authority: AcceptedReadAuthority, limits: DiagramLimits) -> None:
        self.authority, self.limits = authority, limits

    def open_exact(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        member: Literal["spec", "layout", "members", "svg"],
    ) -> VerifiedMemberHandle:
        read_deadline = monotonic() + self.limits.read_seconds
        scope = VersionScope.model_validate(scope)
        reference = ArtifactReference.model_validate(reference)
        if scope != reference.scope or member not in (
            "spec",
            "layout",
            "members",
            "svg",
        ):
            raise ValueError("diagram_scope_mismatch")
        if reference.size_bytes > self.limits.max_manifest_bytes:
            raise ValueError("diagram_limit_exceeded")
        lease = ExitStack()
        try:
            expected = lease.enter_context(self.authority.pinned(scope, reference))
            root = os.open(STORE_ROOT / "sealed", DIRECTORY)
            directory = None
            try:
                directory = os.open(
                    str(reference.generation_id), DIRECTORY, dir_fd=root
                )
                data = _read_hash(
                    directory,
                    "manifest.json",
                    reference.size_bytes,
                    reference.digests.content,
                    deadline=read_deadline,
                )
                manifest = DiagramArtifactManifest.from_bytes(
                    data, max_bytes=self.limits.max_manifest_bytes
                )
                if manifest != expected or manifest.to_bytes() != data:
                    raise ValueError("diagram_integrity_error")
                DiagramArtifactDescriptor(manifest=manifest, reference=reference)
                descriptor = next(m for m in manifest.members if m.member == member)
                cap = {
                    "spec": self.limits.max_spec_bytes,
                    "layout": self.limits.max_layout_bytes,
                    "members": self.limits.max_members_bytes,
                    "svg": self.limits.max_svg_bytes,
                }[member]
                if (
                    descriptor.size_bytes > cap
                    or sum(m.size_bytes for m in manifest.members)
                    > self.limits.max_total_member_bytes
                ):
                    raise ValueError("diagram_limit_exceeded")
                result = _read_hash(
                    directory,
                    descriptor.file_name,
                    descriptor.size_bytes,
                    descriptor.sha256,
                    deadline=read_deadline,
                )
                self.authority.recheck(scope, reference)
                if monotonic() >= read_deadline:
                    raise TimeoutError("diagram_timeout")
                return _VerifiedBytesHandle(
                    result,
                    lease.pop_all(),
                    self.authority,
                    scope,
                    reference,
                    monotonic() + self.limits.stream_seconds,
                )
            except FileNotFoundError as exc:
                raise ValueError("diagram_generation_unavailable") from exc
            finally:
                if directory is not None:
                    os.close(directory)
                os.close(root)
        finally:
            lease.close()


class CandidateArtifactWriter:
    """Fixed, seal-only process invocation. Never grants worker deletion authority."""

    def stage(
        self,
        request: SealRequest,
        manifest: bytes,
        payloads: dict[str, bytes],
        deadline: float,
        checkpoint: Callable[[], None],
    ) -> None:
        expected = {m.member for m in request.members}
        if (
            set(payloads) != expected
            or hashlib.sha256(manifest).hexdigest() != request.manifest_sha256
        ):
            raise ValueError("diagram_integrity_error")
        root = os.open(STORE_ROOT / "staging", DIRECTORY)
        directory = None
        try:
            try:
                os.mkdir(str(request.generation_id), 0o750, dir_fd=root)
            except FileExistsError:
                pass  # An exact same-attempt retry verifies, never overwrites.
            directory = os.open(str(request.generation_id), DIRECTORY, dir_fd=root)
            values: dict[str, bytes] = {
                "manifest.json": manifest,
                **{m.file_name: payloads[m.member] for m in request.members},
            }
            for name, data in values.items():
                checkpoint()
                if monotonic() >= deadline:
                    raise TimeoutError("diagram_timeout")
                try:
                    fd = os.open(
                        name,
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | os.O_CLOEXEC
                        | os.O_NOFOLLOW,
                        0o640,
                        dir_fd=directory,
                    )
                except FileExistsError:
                    if (
                        _read_hash(
                            directory,
                            name,
                            len(data),
                            hashlib.sha256(data).hexdigest(),
                            deadline=deadline,
                        )
                        != data
                    ):
                        raise ValueError("diagram_integrity_error") from None
                    continue
                try:
                    offset = 0
                    while offset < len(data):
                        checkpoint()
                        if monotonic() >= deadline:
                            raise TimeoutError("diagram_timeout")
                        offset += os.write(fd, data[offset : offset + 65536])
                    os.fsync(fd)
                finally:
                    os.close(fd)
            if set(os.listdir(directory)) != set(values):
                raise ValueError("diagram_integrity_error")
            os.fsync(directory)
            os.fsync(root)
        finally:
            if directory is not None:
                os.close(directory)
            os.close(root)

    def seal(
        self, request: SealRequest, deadline: float, checkpoint: Callable[[], None]
    ) -> SealProof:
        data = request.to_bytes()
        if len(data) > 262144:
            raise ValueError("diagram_limit_exceeded")
        output = self._invoke(
            (
                "/usr/bin/sudo",
                "-n",
                "-u",
                "stacksense-artifacts",
                "--",
                "/opt/stacksense/diagram-artifacts/seal-generation",
            ),
            data,
            deadline,
            checkpoint,
        )
        return SealProof.from_bytes(output, max_bytes=65536)

    @staticmethod
    def _invoke(
        command: tuple[str, ...],
        data: bytes,
        deadline: float,
        checkpoint: Callable[[], None],
    ) -> bytes:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"LANG": "C.UTF-8", "TZ": "UTC"},
            close_fds=True,
            start_new_session=True,
        )
        assert (
            process.stdin is not None
            and process.stdout is not None
            and process.stderr is not None
        )
        output, errors = bytearray(), bytearray()
        try:
            for stream in (process.stdin, process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdin, selectors.EVENT_WRITE, "input")
                selector.register(process.stdout, selectors.EVENT_READ, output)
                selector.register(process.stderr, selectors.EVENT_READ, errors)
                offset = 0
                while selector.get_map():
                    checkpoint()
                    if monotonic() >= deadline:
                        raise TimeoutError("diagram_timeout")
                    for key, _ in selector.select(
                        min(0.05, max(0, deadline - monotonic()))
                    ):
                        fd = key.fd
                        if key.data == "input":
                            offset += os.write(fd, data[offset : offset + 65536])
                            if offset == len(data):
                                selector.unregister(key.fileobj)
                                process.stdin.close()
                        else:
                            chunk = os.read(fd, 8192)
                            if not chunk:
                                selector.unregister(key.fileobj)
                            else:
                                key.data.extend(chunk)
                                if len(key.data) > 65536:
                                    raise ValueError("diagram_integrity_error")
            checkpoint()
            if process.wait(timeout=max(0.001, deadline - monotonic())) != 0 or errors:
                raise ValueError("diagram_store_unavailable")
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")
            return bytes(output)
        finally:
            try:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=2)
            finally:
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()

    def verify(self, request: SealRequest, deadline: float) -> None:
        """Independent physical readback of every member before SEALED_VERIFIED."""
        root = os.open(STORE_ROOT / "sealed", DIRECTORY)
        directory = None
        try:
            directory = os.open(str(request.generation_id), DIRECTORY, dir_fd=root)
            entries = (
                ("manifest.json", request.manifest_size, request.manifest_sha256),
                *((m.file_name, m.size_bytes, m.sha256) for m in request.members),
            )
            if set(os.listdir(directory)) != {e[0] for e in entries}:
                raise ValueError("diagram_integrity_error")
            for name, size, sha in entries:
                _read_hash(directory, name, size, sha, deadline=deadline)
        finally:
            if directory is not None:
                os.close(directory)
            os.close(root)


class OperatorArtifactGC:
    """No worker delegation exists for this fixed operator-only command."""

    def delete_reserved(self, generation_id: UUID, deadline: float) -> None:
        if not isinstance(generation_id, UUID):
            raise ValueError("diagram_input_invalid")
        output = CandidateArtifactWriter._invoke(
            (
                "/usr/bin/sudo",
                "-n",
                "-u",
                "stacksense-artifacts",
                "--",
                "/opt/stacksense/diagram-artifacts/gc-generation",
                str(generation_id),
            ),
            b"",
            deadline,
            lambda: None,
        )
        if output:
            raise ValueError("diagram_integrity_error")


class _VerifiedBytesHandle:
    """Preverified bounded bytes; the accepted read pin lives until close/expiry.

    No raw file handle escapes to consumers. The future durable authority must
    enforce the configured pin TTL independently even if a caller abandons this
    handle. This class is not a durable-pin implementation or registration.
    """

    def __init__(
        self,
        content: bytes,
        lease: ExitStack,
        authority: AcceptedReadAuthority,
        scope: VersionScope,
        reference: ArtifactReference,
        deadline: float,
    ) -> None:
        self.content = content
        self.lease = lease
        self.authority, self.scope, self.reference = authority, scope, reference
        self.deadline, self.offset, self.closed = deadline, 0, False

    def read(self, size: int) -> bytes:
        if type(size) is not int or size < 0:
            raise ValueError("diagram_input_invalid")
        if self.closed:
            raise ValueError("diagram_generation_unavailable")
        try:
            if monotonic() >= self.deadline:
                raise TimeoutError("diagram_timeout")
            self.authority.recheck(self.scope, self.reference)
            end = min(self.offset + size, len(self.content))
            result = self.content[self.offset : end]
            self.offset = end
            self.authority.recheck(self.scope, self.reference)
            if monotonic() >= self.deadline:
                raise TimeoutError("diagram_timeout")
            return result
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.content = b""
            self.lease.close()


def _regular(fd: int) -> os.stat_result:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("diagram_integrity_error")
    return info


def _read_hash(
    directory: int,
    name: str,
    size: int,
    expected: str,
    *,
    deadline: float | None = None,
) -> bytes:
    if deadline is not None and monotonic() >= deadline:
        raise TimeoutError("diagram_timeout")
    fd = os.open(name, READONLY, dir_fd=directory)
    try:
        info = _regular(fd)
        if info.st_size != size:
            raise ValueError("diagram_integrity_error")
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            if deadline is not None and monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError("diagram_integrity_error")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1) or _regular(fd).st_size != size:
            raise ValueError("diagram_integrity_error")
        value = b"".join(chunks)
        if hashlib.sha256(value).hexdigest() != expected:
            raise ValueError("diagram_integrity_error")
        if deadline is not None and monotonic() >= deadline:
            raise TimeoutError("diagram_timeout")
        return value
    finally:
        os.close(fd)


def _copy_member(source: int, target: int, name: str, size: int, expected: str) -> None:
    """Copy into a fresh inode; source chmod/rename/old FDs cannot mutate it."""
    incoming = os.open(name, READONLY, dir_fd=source)
    outgoing: int | None = None
    try:
        before = _regular(incoming)
        if before.st_size != size or before.st_dev != os.fstat(source).st_dev:
            raise ValueError("diagram_integrity_error")
        outgoing = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=target,
        )
        digest = hashlib.sha256()
        remaining = size
        while remaining:
            chunk = os.read(incoming, min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError("diagram_integrity_error")
            digest.update(chunk)
            view = memoryview(chunk)
            while view:
                view = view[os.write(outgoing, view) :]
            remaining -= len(chunk)
        after = _regular(incoming)
        if (
            os.read(incoming, 1)
            or after.st_size != size
            or digest.hexdigest() != expected
        ):
            raise ValueError("diagram_integrity_error")
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError("diagram_integrity_error")
        os.fchmod(outgoing, 0o440)
        os.fsync(outgoing)
    finally:
        os.close(incoming)
        if outgoing is not None:
            os.close(outgoing)


def _rename_noreplace(parent: int, source: str, target: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise ValueError("diagram_store_unavailable")
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(parent, source.encode(), parent, target.encode(), 1) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError("diagram generation already exists")
        raise OSError(error, "atomic no-replace unavailable")


class PrincipalSealer:
    def __init__(self, metadata: SealerMetadata, limits: DiagramLimits) -> None:
        artifact_uid = pwd.getpwnam("stacksense-artifacts").pw_uid
        worker_uid = pwd.getpwnam("stacksense-worker").pw_uid
        if os.geteuid() != artifact_uid or artifact_uid in (0, worker_uid):
            raise ValueError("diagram_store_unavailable")
        for path in (STORE_ROOT, STORE_ROOT / "sealed", STORE_ROOT / "locks"):
            for parent in (path, *path.parents):
                info = parent.lstat()
                if (
                    parent.is_symlink()
                    or info.st_mode & 0o022
                    or info.st_uid not in (0, artifact_uid)
                ):
                    raise ValueError("diagram_store_unavailable")
        buffer = ctypes.create_string_buffer(256)
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.statfs(os.fsencode(STORE_ROOT / "sealed"), buffer) != 0:
            raise ValueError("diagram_store_unavailable")
        filesystem = ctypes.c_long.from_buffer(buffer).value
        if filesystem not in (0xEF53, 0x58465342):  # ext4 / XFS only
            raise ValueError("diagram_store_unavailable")
        self.metadata, self.limits = metadata, limits

    @contextmanager
    def _locked(self, generation_id: UUID) -> Iterator[None]:
        root = os.open(STORE_ROOT / "locks", DIRECTORY)
        lock = os.open(
            str(generation_id),
            os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=root,
        )
        try:
            if _regular(lock).st_uid != os.geteuid():
                raise ValueError("diagram_store_unavailable")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(lock)
            os.close(root)

    def _entries(self, request: SealRequest) -> tuple[tuple[str, int, str], ...]:
        caps = {
            "spec": self.limits.max_spec_bytes,
            "layout": self.limits.max_layout_bytes,
            "members": self.limits.max_members_bytes,
            "svg": self.limits.max_svg_bytes,
        }
        if (
            request.manifest_size > self.limits.max_manifest_bytes
            or sum(m.size_bytes for m in request.members)
            > self.limits.max_total_member_bytes
        ):
            raise ValueError("diagram_limit_exceeded")
        for member in request.members:
            if member.size_bytes > caps[member.member]:
                raise ValueError("diagram_limit_exceeded")
        return ("manifest.json", request.manifest_size, request.manifest_sha256), *(
            (m.file_name, m.size_bytes, m.sha256) for m in request.members
        )

    def _verify(self, directory: int, request: SealRequest) -> None:
        entries = self._entries(request)
        if set(os.listdir(directory)) != {e[0] for e in entries}:
            raise ValueError("diagram_integrity_error")
        manifest_bytes = b""
        for name, size, expected in entries:
            data = _read_hash(directory, name, size, expected)
            if name == "manifest.json":
                manifest_bytes = data
        manifest = DiagramArtifactManifest.from_bytes(
            manifest_bytes, max_bytes=self.limits.max_manifest_bytes
        )
        if manifest.to_bytes() != manifest_bytes:
            raise ValueError("diagram_integrity_error")
        work = request.attempt.work
        if (
            manifest.scope != work.scope
            or manifest.binding != work.binding
            or manifest.input_fingerprint != work.input_fingerprint
            or manifest.generation_id != request.generation_id
            or manifest.artifact_id != request.artifact_id
            or manifest.members != request.members
        ):
            raise ValueError("diagram_integrity_error")

    def seal(self, request: SealRequest) -> SealProof:
        request = SealRequest.model_validate(request)
        self._entries(request)
        with self._locked(request.generation_id):
            self.metadata.require_staging(request)
            sealed = os.open(STORE_ROOT / "sealed", DIRECTORY)
            source_root = os.open(STORE_ROOT / "staging", DIRECTORY)
            source: int | None = None
            target: int | None = None
            try:
                try:
                    existing = os.open(
                        str(request.generation_id), DIRECTORY, dir_fd=sealed
                    )
                except FileNotFoundError:
                    existing = None
                if existing is not None:
                    try:
                        self._verify(existing, request)
                        return self._proof(existing, request)
                    finally:
                        os.close(existing)
                source = os.open(
                    str(request.generation_id), DIRECTORY, dir_fd=source_root
                )
                if set(os.listdir(source)) != {e[0] for e in self._entries(request)}:
                    raise ValueError("diagram_integrity_error")
                temporary = ".candidate-" + str(uuid4())
                os.mkdir(temporary, mode=0o700, dir_fd=sealed)
                target = os.open(temporary, DIRECTORY, dir_fd=sealed)
                _proof_checkpoint("before_copy", request.generation_id)
                for name, size, expected in self._entries(request):
                    _copy_member(source, target, name, size, expected)
                    _proof_checkpoint("after_" + name, request.generation_id)
                self._verify(target, request)
                _proof_checkpoint("after_verify", request.generation_id)
                # Recheck committed metadata under the protected lock before
                # placement, including DELETING/DELETED tombstone exclusion.
                self.metadata.require_staging(request)
                os.fchmod(target, 0o550)
                os.fsync(target)
                _proof_checkpoint("after_fsync", request.generation_id)
                _rename_noreplace(sealed, temporary, str(request.generation_id))
                os.fsync(sealed)
                _proof_checkpoint("after_placement", request.generation_id)
                return self._proof(target, request)
            finally:
                for fd in (source, target, source_root, sealed):
                    if fd is not None:
                        os.close(fd)
                # On failure incomplete private inodes are retained/quarantined.
                # No worker delete privilege or unsafe recursive cleanup exists.

    def _proof(self, directory: int, request: SealRequest) -> SealProof:
        info = os.fstat(directory)
        return SealProof(
            verification_version="1.0.0",
            manifest_sha256=request.manifest_sha256,
            member_set_digest=hashlib.sha256(
                canonical_bytes(request.members)
            ).hexdigest(),
            physical_object_id=f"{info.st_dev}:{info.st_ino}",
            sealed_at=datetime.now(UTC),
        )

    def delete_reserved(self, generation_id: UUID) -> None:
        """Only the operator GC entry can call this method, never the seal entry."""
        with self._locked(generation_id):
            self.metadata.require_deleting(generation_id)
            root = os.open(STORE_ROOT / "sealed", DIRECTORY)
            directory: int | None = None
            try:
                try:
                    directory = os.open(str(generation_id), DIRECTORY, dir_fd=root)
                except FileNotFoundError:
                    # Exact retired reservation was independently validated;
                    # this covers interruption after unlink but before tombstone.
                    return
                names = {
                    "manifest.json",
                    "spec.json",
                    "layout.json",
                    "members.json",
                    "scene.svg",
                }
                present = set(os.listdir(directory))
                if not present <= names:
                    raise ValueError("diagram_integrity_error")
                for name in present:
                    fd = os.open(name, READONLY, dir_fd=directory)
                    try:
                        _regular(fd)
                    finally:
                        os.close(fd)
                self.metadata.require_deleting(generation_id)
                os.fchmod(directory, 0o700)
                for name in sorted(present):
                    os.unlink(name, dir_fd=directory)
                os.fsync(directory)
                os.rmdir(str(generation_id), dir_fd=root)
                os.fsync(root)
            finally:
                if directory is not None:
                    os.close(directory)
                os.close(root)
