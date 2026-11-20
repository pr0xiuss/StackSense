"""Opt-in REAL installed Linux proofs. An enabled missing prerequisite fails.

Run as the provisioned non-root worker in its delegated systemd scope:
M4_LINUX_PROOFS=1 python -m pytest -s .../test_linux_deployment.py
No test installs users, mounts, sudo rules, or modifies the installed runtime.
"""

import json
import os
import select
import subprocess
import sys
from time import monotonic, sleep
from uuid import uuid4

import pytest

from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.fonts import DiagramFonts
from backend.platform.diagrams.layout import (
    INSTALL_ROOT,
    ElkLayoutEngine,
    LayoutScene,
    RuntimeEdge,
    RuntimeNode,
    create_layout_profile,
    verify_installation,
)
from backend.platform.diagrams.linux_runtime import delegation_root, job_cgroup
from backend.platform.diagrams.model import visual_id

pytestmark = pytest.mark.skipif(
    os.environ.get("M4_LINUX_PROOFS") != "1",
    reason="opt-in real Linux deployment proof",
)


class Control:
    def __init__(self, cancel_at=None):
        self.cancel_at = cancel_at

    def checkpoint(self):
        if self.cancel_at is not None and monotonic() >= self.cancel_at:
            raise InterruptedError("proof cancellation")


def engine(limits=None):
    assert sys.platform == "linux" and os.geteuid() != 0
    lock = verify_installation()
    assert {"layout_runtime/launch_probe.py", "runtime/root/app/proof_probe.mjs"} <= {
        entry.path for entry in lock.files
    }
    delegation_root()
    fonts = DiagramFonts()
    return (
        ElkLayoutEngine(
            limits or DiagramLimits(), font_manifest_digest=fonts.manifest_digest()
        ),
        lock,
        fonts,
    )


@pytest.mark.parametrize(
    "template,profile",
    [
        ("system_overview", "architecture_compound_v1"),
        ("component_architecture", "architecture_compound_v1"),
        ("dependency_map", "dependency_layered_v1"),
        ("data_flow", "static_flow_v1"),
    ],
)
@pytest.mark.parametrize("count", [0, 20, 150, 500])
def test_real_elk_repeated_geometry(template, profile, count):
    runtime, lock, fonts = engine()
    nodes = tuple(
        RuntimeNode(
            id=visual_id("node", i),
            parent_id=None,
            width=240000,
            height=80000,
            ports=(),
        )
        for i in range(count)
    )
    scene = LayoutScene(
        nodes=nodes,
        edges=tuple(
            RuntimeEdge(
                id=visual_id("edge", i), source=nodes[i].id, target=nodes[i + 1].id
            )
            for i in range(count - 1)
        ),
        labels=(),
    )
    selected = create_layout_profile(profile, lock, fonts.manifest_digest())
    fonts.close()
    expected = None
    for ordinal in range(20):
        started = monotonic()
        result = runtime.layout("a" * 64, selected, scene, started + 30, Control())
        raw = result.geometry.to_bytes()
        if expected is not None:
            assert raw == expected
        expected = raw
        print(
            json.dumps(
                {
                    "proof": "elk",
                    "profile": profile,
                    "template": template,
                    "nodes": count,
                    "ordinal": ordinal,
                    "seconds": monotonic() - started,
                    "bytes": len(raw),
                    "result": "PASS",
                }
            )
        )
    assert not list(delegation_root().glob("diagram-*"))


@pytest.mark.parametrize(
    "mode",
    [
        "denial",
        "fds",
        "scratch",
        "cpu",
        "memory",
        "stdout",
        "stderr",
        "processes",
        "cancel",
    ],
)
def test_real_sandbox_hostile_workloads(mode):
    limits = DiagramLimits(
        max_helper_memory_bytes=(768 if mode == "processes" else 128) * 1024**2,
        max_helper_processes=16 if mode == "processes" else 64,
        max_helper_cpu_seconds=20 if mode == "cancel" else 1,
        max_scratch_bytes=1024**2,
    )
    runtime, _, fonts = engine(limits)
    fonts.close()
    identity, observed = uuid4(), {}
    process = None
    started = monotonic()
    with job_cgroup(identity, limits, observations=observed) as group:
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    str(INSTALL_ROOT / "layout_runtime/launch_probe.py"),
                    str(identity),
                    str(limits.max_helper_memory_bytes),
                    str(limits.max_helper_processes),
                    str(limits.max_helper_fds),
                    str(limits.max_helper_cpu_seconds),
                    str(limits.max_scratch_bytes),
                    str(limits.max_total_member_bytes),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                start_new_session=True,
                env={
                    "LANG": "C.UTF-8",
                    "TZ": "UTC",
                    "HOME": "/nonexistent",
                    "NODE_OPTIONS": "",
                },
            )
            control = Control(started + 1 if mode == "cancel" else None)
            try:
                data = runtime._exchange(
                    process, json.dumps({"mode": mode}).encode(), started + 8, control
                )
                assert mode in ("denial", "fds", "scratch")
                result = json.loads(data)
                if mode == "denial":
                    assert result and all(result.values())
                elif mode == "fds":
                    assert result["code"] == "EMFILE"
                    assert result["count"] < limits.max_helper_fds
                else:
                    assert result["code"] in ("ENOSPC", "EFBIG")
                    assert result["bytes"] <= limits.max_scratch_bytes
            except (TimeoutError, InterruptedError, ValueError) as exc:
                assert str(exc) in (
                    "diagram_limit_exceeded",
                    "diagram_timeout",
                    "proof cancellation",
                )
                assert mode in (
                    "cpu",
                    "memory",
                    "stdout",
                    "stderr",
                    "processes",
                    "cancel",
                )
                assert process.returncode != 78
        finally:
            (group / "cgroup.kill").write_text("1")
            if process is not None:
                process.wait(timeout=2)
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
    assert not (delegation_root() / ("diagram-" + str(identity))).exists()
    if mode == "memory":
        assert (
            int(
                dict(line.split() for line in observed["memory.events"].splitlines())[
                    "oom_kill"
                ]
            )
            > 0
        )
    if mode == "processes":
        assert (
            int(
                dict(line.split() for line in observed["pids.events"].splitlines())[
                    "max"
                ]
            )
            > 0
        )
    print(
        json.dumps(
            {
                "proof": mode,
                "result": "PASS",
                "elapsed": monotonic() - started,
                "cgroup": observed,
            }
        )
    )


@pytest.mark.parametrize("shape", ["compound", "cycle", "disconnected", "high_fanout"])
def test_real_adversarial_geometry_shapes(shape):
    runtime, lock, fonts = engine()
    group = RuntimeNode(
        id=visual_id("group", shape),
        parent_id=None,
        width=240000,
        height=80000,
        ports=(),
    )
    nodes = tuple(
        RuntimeNode(
            id=visual_id("node", i),
            parent_id=group.id if shape == "compound" else None,
            width=240000,
            height=80000,
            ports=(),
        )
        for i in range(20)
    )
    pairs = (
        []
        if shape == "disconnected"
        else (
            [(0, i) for i in range(1, 20)]
            if shape == "high_fanout"
            else [(i, (i + 1) % 20) for i in range(20)]
        )
    )
    scene = LayoutScene(
        nodes=(*nodes, group) if shape == "compound" else nodes,
        edges=tuple(
            RuntimeEdge(id=visual_id("edge", i), source=nodes[a].id, target=nodes[b].id)
            for i, (a, b) in enumerate(pairs)
        ),
        labels=(),
    )
    selected = create_layout_profile(
        "architecture_compound_v1", lock, fonts.manifest_digest()
    )
    fonts.close()
    expected = None
    for ordinal in range(20):
        output = runtime.layout("b" * 64, selected, scene, monotonic() + 30, Control())
        raw = output.geometry.to_bytes()
        if expected is not None:
            assert raw == expected
        expected = raw
        print(
            json.dumps(
                {"proof": "shape", "shape": shape, "ordinal": ordinal, "result": "PASS"}
            )
        )


def test_installed_runtime_cannot_be_modified_by_worker():
    _, lock, fonts = engine()
    fonts.close()
    for entry in lock.files:
        path = INSTALL_ROOT / entry.path
        with pytest.raises(PermissionError):
            # Open without truncating: even an unexpectedly writable file is
            # not altered by this negative test.
            fd = os.open(path, os.O_WRONLY)
            os.close(fd)
    with pytest.raises(PermissionError):
        os.open(
            INSTALL_ROOT / "unauthorized", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )


@pytest.mark.parametrize(
    "wire", [b"", b"\0\0\0\xff{}", b"\0\0\0\x02[]", b"\0\0\0\x02{}", b"\0\0\0\x04null"]
)
def test_real_helper_rejects_malformed_wire_and_reaps(wire):
    runtime, _, fonts = engine()
    fonts.close()
    identity = uuid4()
    limits = DiagramLimits()
    with job_cgroup(identity, limits) as group:
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                str(INSTALL_ROOT / "layout_runtime/launch_elk.py"),
                str(identity),
                str(limits.max_helper_memory_bytes),
                str(limits.max_helper_processes),
                str(limits.max_helper_fds),
                str(limits.max_helper_cpu_seconds),
                str(limits.max_scratch_bytes),
                str(limits.max_total_member_bytes),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,
            env={
                "LANG": "C.UTF-8",
                "TZ": "UTC",
                "HOME": "/nonexistent",
                "NODE_OPTIONS": "",
            },
        )
        try:
            output = runtime._exchange(process, wire, monotonic() + 8, Control())
            assert not output and process.returncode == 1
        finally:
            (group / "cgroup.kill").write_text("1")
            process.wait(timeout=2)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def test_real_worker_parent_death_leaves_no_helper_descendants():
    _, lock, fonts = engine()
    fonts.close()
    assert "layout_runtime/parent_probe.py" in {x.path for x in lock.files}
    identity = uuid4()
    limits = DiagramLimits()
    with job_cgroup(identity, limits) as group:
        parent = subprocess.Popen(
            [
                sys.executable,
                "-I",
                str(INSTALL_ROOT / "layout_runtime/parent_probe.py"),
                str(identity),
                str(limits.max_helper_memory_bytes),
                str(limits.max_helper_processes),
                str(limits.max_helper_fds),
                str(limits.max_helper_cpu_seconds),
                str(limits.max_scratch_bytes),
                str(limits.max_total_member_bytes),
            ],
            stdin=subprocess.DEVNULL,
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
        try:
            assert parent.stdout is not None
            assert select.select([parent.stdout], [], [], 5)[0]
            assert parent.stdout.readline().strip().isdigit()
            assert (group / "cgroup.procs").read_text().strip()
            parent.kill()
            parent.wait(timeout=2)
            until = monotonic() + 2
            while "populated 1" in (group / "cgroup.events").read_text():
                assert monotonic() < until, "helper survived worker death"
                sleep(0.01)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=2)
            if parent.stdout is not None:
                parent.stdout.close()
