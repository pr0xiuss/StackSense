"""Native Windows primitives. Not imported on Linux; no emulated security.

Job limits are resource controls, NOT a filesystem/network sandbox. The LPAC
launcher uses a capability-free token as well. Actual Windows proof remains a
deployment gate; these primitives never register a production capability.
"""

from __future__ import annotations

import ctypes as c
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

U32, U64, SIZE, PTR = c.c_uint32, c.c_uint64, c.c_size_t, c.c_void_p


class SecurityAttributes(c.Structure):
    _fields_ = [("length", U32), ("descriptor", PTR), ("inherit", c.c_int)]


class SidAttributes(c.Structure):
    _fields_ = [("sid", PTR), ("attributes", U32)]


class GroupHeader(c.Structure):
    _fields_ = [("count", U32), ("first", SidAttributes)]


class BasicLimits(c.Structure):
    _fields_ = [
        ("process_time", c.c_int64),
        ("job_time", c.c_int64),
        ("flags", U32),
        ("min_working_set", SIZE),
        ("max_working_set", SIZE),
        ("active_processes", U32),
        ("affinity", SIZE),
        ("priority", U32),
        ("scheduling", U32),
    ]


class IoCounters(c.Structure):
    _fields_ = [
        (name, U64)
        for name in (
            "reads",
            "writes",
            "other",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class ExtendedLimits(c.Structure):
    _fields_ = [
        ("basic", BasicLimits),
        ("io", IoCounters),
        ("process_memory", SIZE),
        ("job_memory", SIZE),
        ("peak_process", SIZE),
        ("peak_job", SIZE),
    ]


class FileInformation(c.Structure):
    _layout_ = "ms"
    _pack_ = 4
    _fields_ = [
        ("attributes", U32),
        ("created", U64),
        ("accessed", U64),
        ("written", U64),
        ("volume", U32),
        ("size_high", U32),
        ("size_low", U32),
        ("links", U32),
        ("index_high", U32),
        ("index_low", U32),
    ]


class NativeWindows:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("native Windows execution required")
        load = vars(c)["WinDLL"]
        self.kernel = load("kernel32", use_last_error=True, winmode=0x800)
        self.advapi = load("advapi32", use_last_error=True, winmode=0x800)
        self.userenv = load("userenv", use_last_error=True, winmode=0x800)

    def api(
        self, library: Any, name: str, args: list[Any], result: Any = c.c_int
    ) -> Any:
        function = getattr(library, name)
        function.argtypes = args
        function.restype = result
        return function

    def check(self, result: Any) -> Any:
        if not result:
            raise vars(c)["WinError"]()
        return result

    def close(self, handle: Any) -> None:
        self.check(self.api(self.kernel, "CloseHandle", [PTR])(handle))

    def token_sid(self) -> str:
        token = PTR()
        process = self.api(self.kernel, "GetCurrentProcess", [], PTR)()
        self.check(
            self.api(self.advapi, "OpenProcessToken", [PTR, U32, PTR])(
                process, 8, c.byref(token)
            )
        )
        try:
            size = U32()
            read = self.api(
                self.advapi, "GetTokenInformation", [PTR, U32, PTR, U32, PTR]
            )
            read(token, 1, None, 0, c.byref(size))
            data = c.create_string_buffer(size.value)
            self.check(read(token, 1, data, size, c.byref(size)))
            return self.sid_string(c.cast(data, c.POINTER(PTR))[0])
        finally:
            self.close(token)

    def require_unprivileged(self) -> None:
        if self.token_sid() == "S-1-5-18":
            raise ValueError("diagram_root_worker_forbidden")
        token = PTR()
        process = self.api(self.kernel, "GetCurrentProcess", [], PTR)()
        self.check(
            self.api(self.advapi, "OpenProcessToken", [PTR, U32, PTR])(
                process, 8, c.byref(token)
            )
        )
        try:
            size = U32()
            read = self.api(
                self.advapi, "GetTokenInformation", [PTR, U32, PTR, U32, PTR]
            )
            read(token, 2, None, 0, c.byref(size))
            data = c.create_string_buffer(size.value)
            self.check(read(token, 2, data, size, c.byref(size)))
            count = U32.from_buffer(data).value
            if count > 1024:
                raise ValueError("diagram_runtime_unavailable")
            for ordinal in range(count):
                offset = GroupHeader.first.offset + ordinal * c.sizeof(SidAttributes)
                group = SidAttributes.from_buffer(data, offset)
                if self.sid_string(group.sid) == "S-1-5-32-544":
                    # Reject even a deny-only/filtered administrator token.
                    raise ValueError("diagram_root_worker_forbidden")
        finally:
            self.close(token)

    def sid_string(self, sid: Any) -> str:
        text = c.c_wchar_p()
        self.check(
            self.api(self.advapi, "ConvertSidToStringSidW", [PTR, PTR])(
                sid, c.byref(text)
            )
        )
        try:
            return str(text.value)
        finally:
            self.api(self.kernel, "LocalFree", [PTR], PTR)(c.cast(text, PTR))

    @contextmanager
    def descriptor(self, sddl: str) -> Iterator[SecurityAttributes]:
        pointer = PTR()
        self.check(
            self.api(
                self.advapi,
                "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                [c.c_wchar_p, U32, PTR, PTR],
            )(sddl, 1, c.byref(pointer), None)
        )
        try:
            yield SecurityAttributes(c.sizeof(SecurityAttributes), pointer, 0)
        finally:
            self.api(self.kernel, "LocalFree", [PTR], PTR)(pointer)

    @contextmanager
    def file(
        self,
        path: Path,
        *,
        write: bool = False,
        new: bool = False,
        directory: bool = False,
        security: SecurityAttributes | None = None,
    ) -> Iterator[Any]:
        # No FILE_SHARE_DELETE: pin parent/file identities through the operation.
        handle = self.api(
            self.kernel, "CreateFileW", [c.c_wchar_p, U32, U32, PTR, U32, U32, PTR], PTR
        )(
            str(path),
            0x40020000 if write else 0x80020000,
            1 if write else 3,
            c.byref(security) if security else None,
            1 if new else 3,
            0x00200000 | (0x02000000 if directory else 0),
            None,
        )
        if handle == PTR(-1).value:
            self.check(False)
        try:
            info = self.information(handle)
            if info.attributes & 0x400 or (not directory and info.links != 1):
                raise ValueError("diagram_integrity_error")
            yield handle
        finally:
            self.close(handle)

    def information(self, handle: Any) -> FileInformation:
        value = FileInformation()
        self.check(
            self.api(self.kernel, "GetFileInformationByHandle", [PTR, PTR])(
                handle, c.byref(value)
            )
        )
        return value

    def require_acl(
        self, handle: Any, owner: str, reader: str | tuple[str, ...]
    ) -> None:
        sid, dacl, sd = PTR(), PTR(), PTR()
        code = self.api(
            self.advapi,
            "GetSecurityInfo",
            [PTR, U32, U32, PTR, PTR, PTR, PTR, PTR],
            U32,
        )(handle, 1, 5, c.byref(sid), None, c.byref(dacl), None, c.byref(sd))
        if code:
            raise OSError(code, "diagram ACL inspection failed")
        try:
            control = c.c_uint16()
            revision = U32()
            self.check(
                self.api(self.advapi, "GetSecurityDescriptorControl", [PTR, PTR, PTR])(
                    sd, c.byref(control), c.byref(revision)
                )
            )
            if self.sid_string(sid) != owner or not dacl or not control.value & 0x1000:
                raise ValueError("diagram_store_unavailable")
            # ACL header: revision/reserved/size/acecount/reserved (8 bytes).
            address = dacl.value
            if address is None:
                raise ValueError("diagram_store_unavailable")
            count = c.c_uint16.from_address(address + 4).value
            if not 1 <= count <= 16:
                raise ValueError("diagram_store_unavailable")
            trusted = {owner, "S-1-5-18", "S-1-5-32-544"}
            for ordinal in range(count):
                ace = PTR()
                self.check(
                    self.api(self.advapi, "GetAce", [PTR, U32, PTR])(
                        dacl, ordinal, c.byref(ace)
                    )
                )
                ace_address = ace.value
                if ace_address is None:
                    raise ValueError("diagram_store_unavailable")
                kind = c.c_ubyte.from_address(ace_address).value
                if kind != 0:
                    raise ValueError("unsupported diagram ACE")
                mask = U32.from_address(ace_address + 4).value
                principal = self.sid_string(PTR(ace_address + 8))
                if principal not in trusted:
                    # Reject generic write/all, DELETE, WRITE_DAC/OWNER and file
                    # create/append/EA/attributes/delete-child rights for reader.
                    readers = (reader,) if isinstance(reader, str) else reader
                    if principal not in readers or mask & 0x500D0156:
                        raise ValueError("diagram_store_unavailable")
        finally:
            self.api(self.kernel, "LocalFree", [PTR], PTR)(sd)

    def read(self, handle: Any, size: int) -> bytes:
        output = bytearray()
        while len(output) <= size:
            amount = min(1024**2, size + 1 - len(output))
            data = c.create_string_buffer(amount)
            done = U32()
            self.check(
                self.api(self.kernel, "ReadFile", [PTR, PTR, U32, PTR, PTR])(
                    handle, data, amount, c.byref(done), None
                )
            )
            if not done.value:
                break
            output.extend(data.raw[: done.value])
        if len(output) != size:
            raise ValueError("diagram_integrity_error")
        return bytes(output)

    def write(self, handle: Any, data: bytes) -> None:
        offset = 0
        while offset < len(data):
            chunk = data[offset : offset + 1024**2]
            done = U32()
            self.check(
                self.api(self.kernel, "WriteFile", [PTR, PTR, U32, PTR, PTR])(
                    handle, c.c_char_p(chunk), len(chunk), c.byref(done), None
                )
            )
            if not done.value:
                raise OSError("zero-byte artifact write")
            offset += done.value
        self.check(self.api(self.kernel, "FlushFileBuffers", [PTR])(handle))

    def require_ntfs(self, handle: Any) -> None:
        filesystem = c.create_unicode_buffer(32)
        self.check(
            self.api(
                self.kernel,
                "GetVolumeInformationByHandleW",
                [PTR, PTR, U32, PTR, PTR, PTR, PTR, U32],
            )(handle, None, 0, None, None, None, filesystem, 32)
        )
        if filesystem.value != "NTFS":
            raise ValueError("diagram_store_unavailable")


class WindowsJob:
    def __init__(
        self, native: NativeWindows, *, memory: int, processes: int, cpu: int
    ) -> None:
        if not (1 <= memory <= 1024**3 and 1 <= processes <= 128 and 1 <= cpu <= 60):
            raise ValueError("diagram_limit_exceeded")
        self.native = native
        self.handle = native.check(
            native.api(native.kernel, "CreateJobObjectW", [PTR, PTR], PTR)(None, None)
        )
        try:
            limits = ExtendedLimits()
            limits.basic.flags = (
                0x2000 | 0x200 | 0x8 | 0x2 | 0x400
            )  # kill/job-memory/process-count/time/die
            limits.basic.active_processes = processes
            limits.basic.process_time = cpu * 10000000
            limits.job_memory = memory
            native.check(
                native.api(
                    native.kernel, "SetInformationJobObject", [PTR, U32, PTR, U32]
                )(self.handle, 9, c.byref(limits), c.sizeof(limits))
            )
            rate = (U32 * 2)(5, max(1, 10000 // (os.cpu_count() or 1)))
            native.check(
                native.api(
                    native.kernel, "SetInformationJobObject", [PTR, U32, PTR, U32]
                )(self.handle, 15, c.byref(rate), c.sizeof(rate))
            )
        except BaseException:
            native.close(self.handle)
            raise

    def assign_suspended(self, process: Any) -> None:
        self.native.check(
            self.native.api(self.native.kernel, "AssignProcessToJobObject", [PTR, PTR])(
                self.handle, process
            )
        )

    def close(self) -> None:
        if self.handle:
            try:
                self.native.check(
                    self.native.api(
                        self.native.kernel, "TerminateJobObject", [PTR, U32]
                    )(self.handle, 1)
                )
            finally:
                self.native.close(self.handle)
                self.handle = None


class StartupInfo(c.Structure):
    _fields_ = [
        ("cb", U32),
        ("reserved", c.c_wchar_p),
        ("desktop", c.c_wchar_p),
        ("title", c.c_wchar_p),
        ("x", U32),
        ("y", U32),
        ("width", U32),
        ("height", U32),
        ("chars_x", U32),
        ("chars_y", U32),
        ("fill", U32),
        ("flags", U32),
        ("show", c.c_uint16),
        ("reserved_size", c.c_uint16),
        ("reserved_bytes", PTR),
        ("stdin", PTR),
        ("stdout", PTR),
        ("stderr", PTR),
    ]


class StartupInfoEx(c.Structure):
    _fields_ = [("startup", StartupInfo), ("attributes", PTR)]


class ProcessInfo(c.Structure):
    _fields_ = [("process", PTR), ("thread", PTR), ("pid", U32), ("tid", U32)]


class SecurityCapabilities(c.Structure):
    _fields_ = [("sid", PTR), ("capabilities", PTR), ("count", U32), ("reserved", U32)]


@contextmanager
def lpac_process(
    native: NativeWindows,
    job: WindowsJob,
    executable: Path,
    entry: Path,
    handles: tuple[int, int, int],
) -> Iterator[ProcessInfo]:
    """No-capability LPAC; suspended before job assignment; exact inherited FDs.

    Provision the dedicated AppContainer profile and immutable RX runtime as
    administrator. No profile/ACL/firewall provisioning occurs during launch.
    """
    import subprocess

    native.require_unprivileged()

    sid = PTR()
    derive = native.api(
        native.userenv,
        "DeriveAppContainerSidFromAppContainerName",
        [c.c_wchar_p, PTR],
        c.c_long,
    )
    if derive("StackSense.Diagrams.B1", c.byref(sid)) != 0:
        raise OSError("diagram_runtime_unavailable")
    attributes = None
    process = ProcessInfo()
    try:
        caps = SecurityCapabilities(sid, None, 0, 0)
        size = SIZE()
        initialize = native.api(
            native.kernel, "InitializeProcThreadAttributeList", [PTR, U32, U32, PTR]
        )
        initialize(None, 3, 0, c.byref(size))
        attributes = c.create_string_buffer(size.value)
        native.check(initialize(attributes, 3, 0, c.byref(size)))
        update = native.api(
            native.kernel,
            "UpdateProcThreadAttribute",
            [PTR, U32, SIZE, PTR, SIZE, PTR, PTR],
        )
        exact_handles = (PTR * 3)(*handles)
        policy = U32(1)  # PROCESS_CREATION_ALL_APPLICATION_PACKAGES_OPT_OUT (LPAC)
        for key, value in (
            (0x20009, caps),
            (0x2000F, policy),
            (0x20002, exact_handles),
        ):
            native.check(
                update(attributes, 0, key, c.byref(value), c.sizeof(value), None, None)
            )
        startup = StartupInfoEx()
        startup.startup.cb = c.sizeof(startup)
        startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
        startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
        startup.attributes = c.cast(attributes, PTR)
        command = c.create_unicode_buffer(
            subprocess.list2cmdline([str(executable), str(entry)])
        )
        environment = c.create_unicode_buffer("LANG=C.UTF-8\0NODE_OPTIONS=\0TZ=UTC\0\0")
        native.check(
            native.api(
                native.kernel,
                "CreateProcessW",
                [c.c_wchar_p, PTR, PTR, PTR, c.c_int, U32, PTR, c.c_wchar_p, PTR, PTR],
            )(
                str(executable),
                command,
                None,
                None,
                True,
                0x80000
                | 0x400
                | 0x4
                | 0x08000000,  # extended + unicode env + suspended + no window
                environment,
                str(entry.parent),
                c.byref(startup),
                c.byref(process),
            )
        )
        job.assign_suspended(process.process)
        token = PTR()
        native.check(
            native.api(native.advapi, "OpenProcessToken", [PTR, U32, PTR])(
                process.process, 8, c.byref(token)
            )
        )
        try:
            read = native.api(
                native.advapi, "GetTokenInformation", [PTR, U32, PTR, U32, PTR]
            )
            for category in (
                29,
                46,
            ):  # TokenIsAppContainer, TokenIsLessPrivilegedAppContainer
                value = U32()
                returned = U32()
                native.check(
                    read(token, category, c.byref(value), 4, c.byref(returned))
                )
                if value.value != 1:
                    raise ValueError("diagram_runtime_unavailable")
        finally:
            native.close(token)
        resumed = native.api(native.kernel, "ResumeThread", [PTR], U32)(process.thread)
        if resumed == 0xFFFFFFFF:
            native.check(False)
        yield process
    finally:
        if process.process:
            job.close()
            native.api(native.kernel, "WaitForSingleObject", [PTR, U32], U32)(
                process.process, 2000
            )
            native.close(process.thread)
            native.close(process.process)
        if attributes is not None:
            native.api(native.kernel, "DeleteProcThreadAttributeList", [PTR], None)(
                attributes
            )
        native.api(native.advapi, "FreeSid", [PTR], PTR)(sid)
