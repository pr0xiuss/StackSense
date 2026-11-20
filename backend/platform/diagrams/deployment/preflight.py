"""Read-only deployment preflight. No provisioning, chmod, DDL or service calls."""

from __future__ import annotations

import json
import os
import platform
import pwd
import shutil
import subprocess
from pathlib import Path

from backend.platform.diagrams.linux_runtime import delegation_root


def inspect() -> dict[str, object]:
    failures: list[str] = []
    for name in ("stacksense-worker", "stacksense-artifacts"):
        try:
            if pwd.getpwnam(name).pw_uid == 0:
                failures.append(name + ": root identity forbidden")
        except KeyError:
            failures.append(name + ": missing")
    root = Path("/opt/stacksense/diagram-artifacts")
    for path in (root, Path("/var/lib/stacksense/diagrams")):
        if not path.is_dir():
            failures.append(str(path) + ": missing")
    filesystem = subprocess.run(
        ["/usr/bin/findmnt", "-no", "FSTYPE", "-T", "/var/lib"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    store = Path("/var/lib/stacksense/diagrams")
    if store.exists():
        filesystem = subprocess.run(
            ["/usr/bin/findmnt", "-no", "FSTYPE", "-T", str(store)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    if filesystem not in ("ext4", "xfs"):
        failures.append("store filesystem must be ext4/XFS, got " + filesystem)
    for tool in ("setfacl", "getfacl", "visudo", "meson", "ninja", "pkg-config"):
        if shutil.which(tool) is None:
            failures.append(tool + ": missing")
    try:
        delegation_root()
    except OSError, ValueError:
        failures.append("worker leaf/delegated empty cgroup root unavailable")
    return {
        "os": platform.platform(),
        "uid": os.geteuid(),
        "filesystem": filesystem,
        "failures": failures,
        "ready": not failures,
    }


if __name__ == "__main__":
    result = inspect()
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["ready"] else 78)
