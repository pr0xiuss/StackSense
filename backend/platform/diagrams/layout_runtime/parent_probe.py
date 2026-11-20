"""Fixed installed disposable worker-parent used ONLY by the B1 death proof."""

import subprocess
import sys

if __name__ == "__main__":
    if len(sys.argv) != 8:
        raise SystemExit(78)
    child = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "/opt/stacksense/diagram-artifacts/layout_runtime/launch_probe.py",
            *sys.argv[1:],
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        env={
            "LANG": "C.UTF-8",
            "TZ": "UTC",
            "HOME": "/nonexistent",
            "NODE_OPTIONS": "",
        },
    )
    assert child.stdin is not None
    child.stdin.write(b'{"mode":"cancel"}')
    child.stdin.close()
    assert child.stdout is not None
    if child.stdout.readline() != b"STARTED\n":
        raise SystemExit(79)
    print(child.pid, flush=True)
    raise SystemExit(child.wait())
