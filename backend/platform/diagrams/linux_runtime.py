"""Linux deployment checks and job cgroups, never lifecycle orchestration."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import monotonic, sleep
from uuid import UUID

from backend.platform.diagrams.configuration import DiagramLimits


def delegation_root() -> Path:
    line = Path("/proc/self/cgroup").read_text().strip()
    if not line.startswith("0::/") or ".." in line:
        raise ValueError("diagram_runtime_unavailable")
    leaf = Path("/sys/fs/cgroup") / line[4:]
    # systemd DelegateSubgroup=worker keeps processes out of the controller root.
    if leaf.name != "worker":
        raise ValueError("diagram_runtime_unavailable")
    parent = leaf.parent
    if (
        parent.is_symlink()
        or parent.stat().st_uid != os.geteuid()
        or parent.stat().st_mode & 0o022
    ):
        raise ValueError("diagram_runtime_unavailable")
    if (parent / "cgroup.procs").read_text().strip():
        raise ValueError("diagram_runtime_unavailable")
    required = {"cpu", "memory", "pids"}
    if not required <= set((parent / "cgroup.subtree_control").read_text().split()):
        raise ValueError("diagram_runtime_unavailable")
    if not os.access(parent, os.W_OK):
        raise ValueError("diagram_runtime_unavailable")
    return parent


def policy(limits: DiagramLimits) -> dict[str, str]:
    return {
        "memory.max": str(limits.max_helper_memory_bytes),
        "memory.swap.max": "0",
        "pids.max": str(limits.max_helper_processes),
        "cpu.max": "100000 100000",
    }


@contextmanager
def job_cgroup(
    identity: UUID, limits: DiagramLimits, *, observations: dict[str, str] | None = None
) -> Iterator[Path]:
    group = delegation_root() / ("diagram-" + str(identity))
    group.mkdir(mode=0o700)
    try:
        for name, value in policy(limits).items():
            (group / name).write_text(value)
            if (group / name).read_text().strip() != value:
                raise ValueError("diagram_runtime_unavailable")
        if not (group / "cgroup.kill").is_file():
            raise ValueError("diagram_runtime_unavailable")
        yield group
    finally:
        if (group / "cgroup.events").read_text().find("populated 1") >= 0:
            (group / "cgroup.kill").write_text("1")
        until = monotonic() + 2
        while "populated 1" in (group / "cgroup.events").read_text():
            if monotonic() >= until:
                raise RuntimeError("diagram_cgroup_cleanup_failed")
            sleep(0.01)
        if observations is not None:
            for name in ("memory.peak", "memory.events", "pids.events", "cpu.stat"):
                observations[name] = (group / name).read_text().strip()
        # Removal failure is a proof failure, never silently ignored.
        group.rmdir()


def protected_regular(path: Path, *, uid: int = 0) -> None:
    for parent in (path, *path.parents):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != uid or info.st_mode & 0o022:
            raise ValueError("diagram_installation_untrusted")
        if parent == path and not stat.S_ISREG(info.st_mode):
            raise ValueError("diagram_installation_untrusted")
