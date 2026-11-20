"""Windows LPAC + Job Object ELK adapter candidate; no production registration.

Actual Windows proof must establish filesystem/network denial AND all resource
ceilings. The presence of this adapter never means Windows is supported.
"""

from __future__ import annotations

import ctypes as c
import hashlib
import struct
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import Any, Literal
from uuid import uuid4

from backend.platform.delivery.contracts import ExecutionControl
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import ClosedRecord, LayoutProfile
from backend.platform.diagrams.layout import (
    LayoutGeometryFailure,
    LayoutOutcome,
    LayoutRequest,
    LayoutScene,
    LockedFile,
    create_layout_profile,
    parse_geometry,
)
from backend.platform.diagrams.windows_native import (
    PTR,
    U32,
    NativeWindows,
    SecurityAttributes,
    WindowsJob,
    lpac_process,
)

ROOT = Path(r"C:\Program Files\StackSense\DiagramRuntime")


class WindowsRuntimeLock(ClosedRecord):
    version: Literal["1.0.0"]
    node: Literal["24.22.3"]
    elkjs: Literal["0.12.1"]
    files: tuple[LockedFile, ...]


def installed(native: NativeWindows, app_sid: str) -> WindowsRuntimeLock:
    owner = "S-1-5-32-544"
    readers = (native.token_sid(), app_sid)
    with native.file(ROOT, directory=True) as root:
        native.require_acl(root, owner, readers)
        native.require_ntfs(root)
        with native.file(ROOT / "runtime-lock.json") as handle:
            native.require_acl(handle, owner, readers)
            info = native.information(handle)
            size = (info.size_high << 32) | info.size_low
            if size > 65536:
                raise ValueError("diagram_runtime_unavailable")
            lock = WindowsRuntimeLock.from_bytes(
                native.read(handle, size), max_bytes=65536
            )
        names = {entry.path for entry in lock.files}
        if (
            not {"node.exe", "elk_layout.mjs", "node_modules/elkjs/lib/elk.bundled.js"}
            <= names
        ):
            raise ValueError("diagram_runtime_unavailable")
        if len(names) != len(lock.files):
            raise ValueError("diagram_runtime_unavailable")
        for entry in lock.files:
            relative = Path(entry.path)
            if relative.is_absolute() or any(
                x in entry.path for x in ("..", ":", "\\")
            ):
                raise ValueError("diagram_runtime_unavailable")
            parents = list((ROOT / relative).parents)
            for parent in reversed(parents[: parents.index(ROOT)]):
                with native.file(parent, directory=True) as directory:
                    native.require_acl(directory, owner, readers)
            with native.file(ROOT / relative) as handle:
                native.require_acl(handle, owner, readers)
                info = native.information(handle)
                size = (info.size_high << 32) | info.size_low
                if size > 128 * 1024**2:
                    raise ValueError("diagram_runtime_unavailable")
                if (
                    hashlib.sha256(native.read(handle, size)).hexdigest()
                    != entry.sha256
                ):
                    raise ValueError("diagram_runtime_unavailable")
    return lock


def appcontainer_sid(native: NativeWindows) -> str:
    pointer = PTR()
    result = native.api(
        native.userenv,
        "DeriveAppContainerSidFromAppContainerName",
        [c.c_wchar_p, PTR],
        c.c_long,
    )("StackSense.Diagrams.B1", c.byref(pointer))
    if result:
        raise OSError("diagram_runtime_unavailable")
    try:
        return native.sid_string(pointer)
    finally:
        native.api(native.advapi, "FreeSid", [PTR], PTR)(pointer)


def communicate(
    native: NativeWindows,
    job: WindowsJob,
    payload: bytes,
    deadline: float,
    control: ExecutionControl,
    limits: DiagramLimits,
    *,
    proof: bool = False,
) -> bytes:
    """Bounded anonymous pipes with explicit inherited handle list; kill+join.

    Threaded Windows pipe I/O is cancelled by terminating the entire job and
    closing pipe handles. A surviving thread is a hard failure, not ignored.
    """
    if proof:
        with native.file(ROOT / "proof-enabled") as marker:
            native.require_acl(marker, "S-1-5-32-544", native.token_sid())
            if native.read(marker, 19) != b"B1-ISOLATED-PROOFS\n":
                raise ValueError("diagram_runtime_unavailable")
    handles: list[Any] = []
    attributes = SecurityAttributes(c.sizeof(SecurityAttributes), None, 1)

    def pipe() -> tuple[Any, Any]:
        read, write = PTR(), PTR()
        native.check(
            native.api(native.kernel, "CreatePipe", [PTR, PTR, PTR, U32])(
                c.byref(read), c.byref(write), c.byref(attributes), 0
            )
        )
        handles.extend((read.value, write.value))
        return read.value, write.value

    stdin_read, stdin_write = pipe()
    stdout_read, stdout_write = pipe()
    stderr_read, stderr_write = pipe()
    for handle in (stdin_write, stdout_read, stderr_read):
        native.check(
            native.api(native.kernel, "SetHandleInformation", [PTR, U32, U32])(
                handle, 1, 0
            )
        )
    errors: list[BaseException] = []
    outputs = [bytearray(), bytearray()]
    done = Event()

    def reader(handle: Any, target: bytearray, cap: int) -> None:
        try:
            while True:
                data = c.create_string_buffer(65536)
                count = U32()
                if not native.api(native.kernel, "ReadFile", [PTR, PTR, U32, PTR, PTR])(
                    handle, data, 65536, c.byref(count), None
                ):
                    error = vars(c)["get_last_error"]()
                    if error == 109:
                        break  # ERROR_BROKEN_PIPE
                    native.check(False)
                if not count.value:
                    break
                if len(target) + count.value > cap:
                    raise ValueError("diagram_limit_exceeded")
                target.extend(data.raw[: count.value])
        except BaseException as exc:
            errors.append(exc)
            done.set()

    def writer() -> None:
        try:
            offset = 0
            while offset < len(payload):
                chunk = payload[offset : offset + 65536]
                count = U32()
                native.check(
                    native.api(native.kernel, "WriteFile", [PTR, PTR, U32, PTR, PTR])(
                        stdin_write, c.c_char_p(chunk), len(chunk), c.byref(count), None
                    )
                )
                if not count.value:
                    raise OSError("diagram input pipe closed")
                offset += count.value
        except BaseException as exc:
            errors.append(exc)
            done.set()
        finally:
            native.close(stdin_write)
            handles.remove(stdin_write)

    threads = [
        Thread(target=writer),
        Thread(
            target=reader,
            args=(stdout_read, outputs[0], limits.max_helper_output_bytes + 4),
        ),
        Thread(
            target=reader,
            args=(stderr_read, outputs[1], limits.max_helper_stderr_bytes),
        ),
    ]
    try:
        with lpac_process(
            native,
            job,
            ROOT / "node.exe",
            ROOT / ("proof_probe.mjs" if proof else "elk_layout.mjs"),
            (stdin_read, stdout_write, stderr_write),
        ) as process:
            for handle in (stdin_read, stdout_write, stderr_write):
                native.close(handle)
                handles.remove(handle)
            for thread in threads:
                thread.start()
            while True:
                control.checkpoint()
                if monotonic() >= deadline:
                    raise TimeoutError("diagram_timeout")
                if errors:
                    raise errors[0]
                state = native.api(
                    native.kernel, "WaitForSingleObject", [PTR, U32], U32
                )(process.process, 50)
                if state == 0:
                    break
                if state != 258:
                    native.check(False)
            for thread in threads:
                thread.join(timeout=max(0, deadline - monotonic()))
            if errors:
                raise errors[0]
            if any(thread.is_alive() for thread in threads):
                raise TimeoutError("diagram_timeout")
            return bytes(outputs[0])
    finally:
        job.close()
        for thread in threads:
            if thread.is_alive() and thread.native_id is not None:
                handle = native.api(
                    native.kernel, "OpenThread", [U32, c.c_int, U32], PTR
                )(1, False, thread.native_id)
                if handle:
                    try:
                        native.api(native.kernel, "CancelSynchronousIo", [PTR])(handle)
                    finally:
                        native.close(handle)
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=2)
        for handle in handles:
            native.close(handle)
        if any(thread.is_alive() for thread in threads):
            raise RuntimeError("diagram_windows_pipe_cleanup_failed")


class WindowsElkEngine:
    def __init__(self, limits: DiagramLimits, *, font_manifest_digest: str) -> None:
        self.limits, self.font_digest = limits, font_manifest_digest

    def layout(
        self,
        spec_digest: str,
        profile: LayoutProfile,
        scene: LayoutScene,
        deadline: float,
        control: ExecutionControl,
    ) -> LayoutOutcome:
        native = NativeWindows()
        native.require_unprivileged()
        lock = installed(native, appcontainer_sid(native))
        deadline = min(deadline, monotonic() + self.limits.helper_wall_seconds)
        scene = LayoutScene.model_validate(scene)
        if (
            sum(n.id.startswith("dn:") for n in scene.nodes) > self.limits.max_nodes
            or sum(n.id.startswith("dg:") for n in scene.nodes) > self.limits.max_groups
            or len(scene.edges) > self.limits.max_edges
        ):
            raise ValueError("diagram_limit_exceeded")
        if profile != create_layout_profile(profile.id, lock, self.font_digest):
            raise ValueError("diagram_integrity_error")
        selected = profile
        for ordinal in range(2):
            control.checkpoint()
            request = LayoutRequest(
                protocol_version=1,
                request_id=uuid4(),
                semantic_digest=spec_digest,
                profile=selected,
                **scene.model_dump(),
            )
            raw = request.to_bytes()
            if len(raw) > self.limits.max_helper_input_bytes:
                raise ValueError("diagram_limit_exceeded")
            job = WindowsJob(
                native,
                memory=self.limits.max_helper_memory_bytes,
                processes=self.limits.max_helper_processes,
                cpu=self.limits.max_helper_cpu_seconds,
            )
            try:
                output = communicate(
                    native,
                    job,
                    struct.pack("!I", len(raw)) + raw,
                    deadline,
                    control,
                    self.limits,
                )
                geometry = parse_geometry(output, request, self.limits)
                return LayoutOutcome(
                    geometry, selected, "none" if ordinal == 0 else "simple_layered"
                )
            except LayoutGeometryFailure:
                if ordinal or selected.id == "simple_layered_v1":
                    raise
                selected = create_layout_profile(
                    "simple_layered_v1", lock, self.font_digest
                )
            finally:
                job.close()
        raise ValueError("diagram_integrity_error")
