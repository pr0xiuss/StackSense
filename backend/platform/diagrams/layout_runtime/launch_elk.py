"""Fixed installed launcher, stdlib only. Never imported by application startup.

This file is installed root-owned under /opt and is invoked with Python -I.
It must not be executed against a repository-writable runtime installation.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import errno
import json
import os
import platform
import resource
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path("/opt/stacksense/diagram-artifacts")


def trusted(path: Path) -> None:
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("untrusted runtime path")
        info = parent.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("runtime must be root-owned and non-writable")


def seccomp_fd() -> int:
    path = ROOT / "layout_runtime" / "seccomp_policy.json"
    trusted(path)
    policy = json.loads(path.read_bytes())
    if platform.machine() not in policy["architectures"]:
        raise ValueError("unsupported sandbox architecture")
    library = ctypes.util.find_library("seccomp")
    if not library:
        raise ValueError("seccomp unavailable")
    lib = ctypes.CDLL(library, use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.seccomp_export_bpf.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]

    class Comparison(ctypes.Structure):
        _fields_ = [
            ("arg", ctypes.c_uint),
            ("op", ctypes.c_int),
            ("mask", ctypes.c_uint64),
            ("value", ctypes.c_uint64),
        ]

    lib.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(Comparison),
    ]
    lib.seccomp_rule_add_array.restype = ctypes.c_int
    context = lib.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise ValueError("seccomp initialization failed")
    fd = os.memfd_create("diagram-seccomp", os.MFD_CLOEXEC)
    try:
        for name in policy["deny"]:
            number = lib.seccomp_syscall_resolve_name(name.encode("ascii"))
            if (
                number >= 0
                and lib.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0)
                != 0
            ):
                raise ValueError("seccomp rule failure")
        clone = lib.seccomp_syscall_resolve_name(b"clone")
        if clone >= 0:
            for flag in policy["clone_namespace_flags"]:
                comparison = Comparison(0, 7, flag, flag)  # MASKED_EQ
                if (
                    lib.seccomp_rule_add_array(
                        context,
                        0x00050000 | errno.EPERM,
                        clone,
                        1,
                        ctypes.byref(comparison),
                    )
                    != 0
                ):
                    raise ValueError("seccomp clone rule failure")
        clone3 = lib.seccomp_syscall_resolve_name(b"clone3")
        if (
            clone3 >= 0
            and lib.seccomp_rule_add(
                context, 0x00050000 | policy["clone3_errno"], clone3, 0
            )
            != 0
        ):
            raise ValueError("seccomp clone3 rule failure")
        if lib.seccomp_export_bpf(context, fd) != 0:
            raise ValueError("seccomp export failure")
        os.lseek(fd, 0, os.SEEK_SET)
        os.set_inheritable(fd, True)  # bwrap consumes it before Node exec
        return fd
    except BaseException:
        os.close(fd)
        raise
    finally:
        lib.seccomp_release(context)


def main(*, proof: bool = False) -> None:
    if os.geteuid() == 0 or len(sys.argv) != 8:
        raise ValueError("invalid unprivileged launcher invocation")
    generation = str(UUID(sys.argv[1]))
    if generation != sys.argv[1]:
        raise ValueError("invalid generation")
    memory, pids, fds, cpu, scratch, file_size = map(int, sys.argv[2:])
    if not (
        1 <= memory <= 1024**3
        and 1 <= pids <= 128
        and 3 <= fds <= 128
        and 1 <= cpu <= 60
        and 1 <= scratch <= 64 * 1024**2
        and 1 <= file_size <= 128 * 1024**2
    ):
        raise ValueError("invalid sandbox limits")
    for path in (ROOT / "bin" / "bwrap", ROOT / "runtime" / "root"):
        trusted(path)
    cgroup_line = Path("/proc/self/cgroup").read_text().strip()
    if not cgroup_line.startswith("0::/") or ".." in cgroup_line:
        raise ValueError("cgroup v2 unavailable")
    leaf = Path("/sys/fs/cgroup") / cgroup_line[4:]
    if leaf.name != "worker":
        raise ValueError("worker delegation leaf missing")
    parent = leaf.parent
    if (parent / "cgroup.procs").read_text().strip():
        raise ValueError("delegation root contains processes")
    group = parent / ("diagram-" + generation)
    # Parent created and configured this exact generation before launch.
    checks = {
        "memory.max": str(memory),
        "memory.swap.max": "0",
        "pids.max": str(pids),
        "cpu.max": "100000 100000",
    }
    for name, expected in checks.items():
        if (group / name).read_text().strip() != expected:
            raise ValueError("cgroup policy mismatch")
    (group / "cgroup.procs").write_text(str(os.getpid()))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (fds, fds))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_size, file_size))
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise ValueError("no-new-privileges failed")
    fd = seccomp_fd()
    argv = [
        str(ROOT / "bin" / "bwrap"),
        "--die-with-parent",
        "--new-session",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-net",
        "--cap-drop",
        "ALL",
        "--ro-bind",
        str(ROOT / "runtime" / "root"),
        "/",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--size",
        str(scratch),
        "--tmpfs",
        "/tmp",
        "--clearenv",
        "--setenv",
        "LANG",
        "C.UTF-8",
        "--setenv",
        "TZ",
        "UTC",
        "--setenv",
        "HOME",
        "/nonexistent",
        "--setenv",
        "NODE_OPTIONS",
        "",
        "--chdir",
        "/tmp",
        "--seccomp",
        str(fd),
        "--",
        "/bin/node",
        "/app/proof_probe.mjs" if proof else "/app/elk_layout.mjs",
    ]
    if proof:
        marker = ROOT / "deployment" / "proof-enabled"
        trusted(marker)
        if marker.read_bytes() != b"B1-ISOLATED-PROOFS\n":
            raise ValueError("proof execution not provisioned")
    os.execve(
        argv[0],
        argv,
        {"LANG": "C.UTF-8", "TZ": "UTC", "HOME": "/nonexistent", "NODE_OPTIONS": ""},
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Deliberately no filesystem names, environment or raw exception output.
        sys.stderr.write("diagram_runtime_unavailable\n")
        raise SystemExit(78) from None
