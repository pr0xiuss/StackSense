"""Kernel-enforced isolation primitives for parser child processes."""

from __future__ import annotations

import ctypes
import errno
import math
import os
import platform
import socket

try:
    import resource
except ImportError:
    resource = None  # type: ignore[assignment]


class ParserSandboxError(RuntimeError):
    """Raised when the mandatory parser sandbox cannot be established."""


_SCMP_ACT_ALLOW = 0x7FFF0000
_SCMP_ACT_ERRNO = 0x00050000
_PR_SET_NO_NEW_PRIVS = 38

_NETWORK_SYSCALLS = (
    "socket",
    "socketpair",
    "connect",
    "bind",
    "listen",
    "accept",
    "accept4",
    "sendto",
    "sendmsg",
    "sendmmsg",
    "recvfrom",
    "recvmsg",
    "recvmmsg",
    "shutdown",
    "getsockname",
    "getpeername",
    "getsockopt",
    "setsockopt",
)

_FILESYSTEM_SYSCALLS = (
    "open",
    "openat",
    "openat2",
    "creat",
    "name_to_handle_at",
    "open_by_handle_at",
    "truncate",
    "truncate64",
    "mkdir",
    "mkdirat",
    "mknod",
    "mknodat",
    "unlink",
    "unlinkat",
    "rename",
    "renameat",
    "renameat2",
    "link",
    "linkat",
    "symlink",
    "symlinkat",
    "chmod",
    "fchmodat",
    "chown",
    "lchown",
    "fchownat",
    "mount",
    "umount2",
    "pivot_root",
    "chroot",
)


def _set_hard_limit(limit_name: str, value: int) -> None:
    if resource is None:
        raise ParserSandboxError(f"{limit_name} is unavailable")
    limit = getattr(resource, limit_name, None)
    if limit is None:
        raise ParserSandboxError(f"{limit_name} is unavailable")
    try:
        resource.setrlimit(limit, (value, value))
    except (OSError, ValueError) as exc:
        raise ParserSandboxError(f"Unable to apply {limit_name}: {exc}") from exc


def _apply_resource_limits(max_memory_mb: int, cpu_seconds: float) -> None:
    if max_memory_mb <= 0 or cpu_seconds <= 0:
        raise ParserSandboxError("Parser sandbox limits must be positive")

    _set_hard_limit("RLIMIT_AS", max_memory_mb * 1024 * 1024)
    _set_hard_limit("RLIMIT_CPU", max(1, math.ceil(cpu_seconds)))
    _set_hard_limit("RLIMIT_FSIZE", 0)
    _set_hard_limit("RLIMIT_CORE", 0)
    _set_hard_limit("RLIMIT_NOFILE", 16)
    _set_hard_limit("RLIMIT_NPROC", 1)


def _load_seccomp() -> ctypes.CDLL:
    try:
        library = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as exc:
        raise ParserSandboxError("libseccomp is unavailable") from exc

    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    library.seccomp_release.restype = None
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    library.seccomp_rule_add.restype = ctypes.c_int
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    return library


def _apply_seccomp_filter() -> None:
    library = _load_seccomp()
    context = library.seccomp_init(_SCMP_ACT_ALLOW)
    if not context:
        raise ParserSandboxError("seccomp_init failed")

    try:
        deny_action = _SCMP_ACT_ERRNO | errno.EPERM
        resolved_network = 0
        resolved_filesystem = 0
        for syscall_name in (*_NETWORK_SYSCALLS, *_FILESYSTEM_SYSCALLS):
            syscall_number = library.seccomp_syscall_resolve_name(
                syscall_name.encode("ascii")
            )
            if syscall_number < 0:
                continue
            result = library.seccomp_rule_add(context, deny_action, syscall_number, 0)
            if result != 0:
                raise ParserSandboxError(
                    f"Unable to deny syscall {syscall_name}: {result}"
                )
            if syscall_name in _NETWORK_SYSCALLS:
                resolved_network += 1
            else:
                resolved_filesystem += 1

        if resolved_network == 0 or resolved_filesystem == 0:
            raise ParserSandboxError("Required seccomp syscall groups are unavailable")

        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl.argtypes = [
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        libc.prctl.restype = ctypes.c_int
        if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            error_number = ctypes.get_errno()
            raise ParserSandboxError(
                f"PR_SET_NO_NEW_PRIVS failed: {os.strerror(error_number)}"
            )

        result = library.seccomp_load(context)
        if result != 0:
            raise ParserSandboxError(f"seccomp_load failed: {result}")
    finally:
        library.seccomp_release(context)


def apply_parser_sandbox(max_memory_mb: int, cpu_seconds: float) -> None:
    """Apply mandatory resource, network, and filesystem restrictions.

    Linux is the supported production worker platform. Other platforms fail
    closed until an equivalent kernel-enforced adapter is implemented.
    """

    if platform.system() != "Linux":
        raise ParserSandboxError(
            "No kernel-enforced parser sandbox is available for this platform"
        )
    _apply_resource_limits(max_memory_mb=max_memory_mb, cpu_seconds=cpu_seconds)
    _apply_seccomp_filter()


def verify_parser_sandbox() -> None:
    """Verify that network creation and host-file opening are kernel-denied."""

    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError as exc:
        if exc.errno not in (errno.EPERM, errno.EACCES):
            raise ParserSandboxError(
                f"Unexpected network-isolation error: {exc}"
            ) from exc
    else:
        raise ParserSandboxError("Parser sandbox still permits network sockets")

    try:
        with open("/etc/passwd", "rb"):
            pass
    except OSError as exc:
        if exc.errno not in (errno.EPERM, errno.EACCES):
            raise ParserSandboxError(
                f"Unexpected filesystem-isolation error: {exc}"
            ) from exc
    else:
        raise ParserSandboxError("Parser sandbox still permits host-file access")
