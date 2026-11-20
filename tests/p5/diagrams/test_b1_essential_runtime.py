"""Real rootless B1 compatibility experiments, not production certification.

Only fixed helper assets enter the mount/network namespace. prlimit bounds
CPU, data allocations, file descriptors and file size; the parent bounds pipes,
wall time and cancellation and reaps the process group. This deliberately does
not assert cgroup RSS accounting, principal separation or production readiness.
"""

import os
import signal
import struct
import subprocess
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pytest

from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.layout import (
    ElkLayoutEngine,
    LayoutRequest,
    RuntimeEdge,
    RuntimeLabel,
    RuntimeNode,
    RuntimePort,
    parse_geometry,
)
from backend.platform.diagrams.model import visual_id
from tests.p5.diagrams.test_layout_runtime import request

pytestmark = pytest.mark.skipif(
    os.environ.get("M4_B1_ESSENTIAL_PROOFS") != "1",
    reason="opt-in real rootless ELK compatibility experiment",
)
ASSETS = (
    Path(__file__).resolve().parents[3] / "backend/platform/diagrams/layout_runtime"
)


class Control:
    def __init__(self, cancel_at=None):
        self.cancel_at = cancel_at

    def checkpoint(self):
        if self.cancel_at is not None and monotonic() >= self.cancel_at:
            raise InterruptedError("cancelled")


def execute(value, *, timeout=30, control=None, probe=False, cpu_seconds=20):
    # Explicit opt-in paths; no implicit developer fallback in production code.
    node = Path(os.environ["M4_B1_NODE"]).resolve(strict=True)
    bwrap = Path(os.environ["M4_B1_BWRAP"]).resolve(strict=True)
    assert subprocess.check_output([node, "--version"]).strip() == b"v24.22.3"
    assert subprocess.check_output([bwrap, "--version"]).strip() == b"bubblewrap 0.12.0"
    command = [
        "/usr/bin/prlimit",
        "--data=1073741824",
        f"--cpu={cpu_seconds}",
        "--nofile=64",
        "--fsize=134217728",
        "--core=0",
        str(bwrap),
        "--unshare-all",
        "--die-with-parent",
        "--cap-drop",
        "ALL",
        "--ro-bind",
        "/usr/lib64",
        "/usr/lib64",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--ro-bind",
        str(node),
        "/node",
        "--ro-bind",
        str(ASSETS / "node_modules/elkjs"),
        "/app/node_modules/elkjs",
        "--ro-bind",
        str(ASSETS / ("proof_probe.mjs" if probe else "elk_layout.mjs")),
        "/app/entry.mjs",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--size",
        "16777216",
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
        "--chdir",
        "/tmp",
        "--",
        "/node",
        "/app/entry.mjs",
    ]
    engine = ElkLayoutEngine(DiagramLimits(), font_manifest_digest="a" * 64)
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        start_new_session=True,
        env={"LANG": "C.UTF-8", "TZ": "UTC"},
    )
    try:
        output = engine._exchange(
            process, value, monotonic() + timeout, control or Control()
        )
        return output, process.returncode
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def scene(profile, count, compound=False):
    base = request()
    group = visual_id("group", "container")
    nodes = tuple(
        RuntimeNode(
            id=visual_id("node", i),
            parent_id=group if compound and i < 2 else None,
            width=240000,
            height=80000,
            ports=(RuntimePort(id=visual_id("port", i), side="SOUTH", order=0),),
        )
        for i in range(count)
    )
    labels = tuple(
        RuntimeLabel(id=visual_id("label", i), owner_id=n.id, width=80000, height=18000)
        for i, n in enumerate(nodes)
    )
    if compound:
        nodes += (
            RuntimeNode(id=group, parent_id=None, width=240000, height=80000, ports=()),
        )
    return LayoutRequest(
        protocol_version=1,
        request_id=uuid4(),
        semantic_digest=base.semantic_digest,
        profile=base.profile.model_copy(update={"id": profile}),
        nodes=nodes,
        edges=tuple(
            RuntimeEdge(
                id=visual_id("edge", i), source=nodes[i].id, target=nodes[i + 1].id
            )
            for i in range(count - 1)
        ),
        labels=labels,
    )


@pytest.mark.parametrize(
    "profile",
    [
        "architecture_compound_v1",
        "dependency_layered_v1",
        "static_flow_v1",
        "simple_layered_v1",
    ],
)
@pytest.mark.parametrize("count", [0, 20, 150, 500])
def test_real_elk_profiles_are_complete_and_repeatable(profile, count):
    value = scene(profile, count)
    expected = None
    started = monotonic()
    for _ in range(3):
        data = value.to_bytes()
        raw, status = execute(struct.pack("!I", len(data)) + data)
        geometry = parse_geometry(raw, value, DiagramLimits())
        assert status == 0
        assert len(geometry.nodes) == count
        assert len(geometry.routes) == max(0, count - 1)
        if expected is not None:
            assert geometry.to_bytes() == expected
        expected = geometry.to_bytes()
    print(
        {
            "profile": profile,
            "nodes": count,
            "runs": 3,
            "seconds": monotonic() - started,
        }
    )


@pytest.mark.parametrize("profile", ["architecture_compound_v1", "simple_layered_v1"])
def test_real_compound_cross_group_routes(profile):
    value = scene(profile, 4, compound=True)
    data = value.to_bytes()
    raw, status = execute(struct.pack("!I", len(data)) + data)
    geometry = parse_geometry(raw, value, DiagramLimits())
    assert status == 0 and len(geometry.groups) == 1
    assert len(geometry.nodes) == 4 and len(geometry.routes) == 3


@pytest.mark.parametrize("shape", ["disconnected", "star", "nested", "cycle"])
def test_real_topologies_preserve_routes_labels_and_order(shape):
    value = scene("architecture_compound_v1", 8, compound=shape == "nested")
    if shape == "disconnected":
        value = value.model_copy(update={"edges": ()})
    if shape == "star":
        value = value.model_copy(
            update={
                "edges": tuple(
                    RuntimeEdge(
                        id=visual_id("edge", i),
                        source=value.nodes[0].id,
                        target=value.nodes[i].id,
                    )
                    for i in range(1, 8)
                )
            }
        )
    if shape == "cycle":
        value = value.model_copy(
            update={
                "edges": (
                    *value.edges,
                    RuntimeEdge(
                        id=visual_id("edge", "cycle"),
                        source=value.nodes[7].id,
                        target=value.nodes[0].id,
                    ),
                )
            }
        )
    if shape == "nested":
        outer = RuntimeNode(
            id=visual_id("group", "outer"),
            parent_id=None,
            width=240000,
            height=80000,
            ports=(),
        )
        value = value.model_copy(
            update={
                "nodes": tuple(
                    (
                        n.model_copy(update={"parent_id": outer.id})
                        if n.id.startswith("dg:")
                        else n
                    )
                    for n in value.nodes
                )
                + (outer,)
            }
        )
    edge_labels = tuple(
        RuntimeLabel(
            id=visual_id("label", edge.id), owner_id=edge.id, width=90000, height=18000
        )
        for edge in value.edges
    )
    value = value.model_copy(update={"labels": value.labels + edge_labels})
    expected = None
    for current in (
        value,
        value.model_copy(
            update={
                "nodes": tuple(reversed(value.nodes)),
                "edges": tuple(reversed(value.edges)),
                "labels": tuple(reversed(value.labels)),
            }
        ),
    ):
        data = current.to_bytes()
        output, status = execute(struct.pack("!I", len(data)) + data)
        geometry = parse_geometry(output, current, DiagramLimits())
        assert status == 0
        # ELK must actually place measured edge labels, not leave absent-text
        # placeholders stacked at the component origin. Exercise real ELK,
        # including compound/cross-group, cyclic and self-loop geometries.
        for label in geometry.labels:
            if label.owner_id.startswith("de:"):
                assert (label.box.x, label.box.y) != (0, 0)
        if expected is not None:
            assert geometry.to_bytes() == expected
        expected = geometry.to_bytes()


@pytest.mark.parametrize("mode", ["timeout", "cancel", "stdout", "stderr"])
def test_real_resource_failure_cancels_and_reaps(mode):
    import json

    payload = json.dumps(
        {"mode": "cancel" if mode in ("timeout", "cancel") else mode}
    ).encode()
    started = monotonic()
    expected = (
        InterruptedError
        if mode == "cancel"
        else TimeoutError if mode == "timeout" else ValueError
    )
    with pytest.raises(expected):
        execute(
            payload,
            timeout=0.5 if mode == "timeout" else 3,
            control=Control(started + 0.5) if mode == "cancel" else None,
            probe=True,
        )
    assert monotonic() - started < 5


def test_real_malformed_input_is_not_success():
    with pytest.raises(ValueError, match="diagram_runtime_unavailable"):
        execute(b"\0\0\0\x02{}")


@pytest.mark.parametrize("mode", ["fds", "scratch", "cpu", "memory"])
def test_real_basic_resource_limits(mode):
    import json

    payload = json.dumps({"mode": mode}).encode()
    if mode in ("cpu", "memory"):
        with pytest.raises(ValueError):
            execute(payload, probe=True, cpu_seconds=1, timeout=5)
    else:
        output, status = execute(payload, probe=True)
        value = json.loads(output)
        assert status == 0
        if mode == "fds":
            assert value["code"] == "EMFILE" and value["count"] < 64
        else:
            assert value["code"] == "ENOSPC" and value["bytes"] <= 16777216
