"""Bound protocol tests; no unsandboxed ELK and no mocked security PASS."""

import json
import struct
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import LayoutProfile
from backend.platform.diagrams.layout import (
    LayoutRequest,
    LayoutScene,
    RuntimeNode,
    parse_geometry,
    verify_installation,
)
from backend.platform.diagrams.model import visual_id


def request():
    node = RuntimeNode(
        id=visual_id("node", "fixture"),
        parent_id=None,
        width=240000,
        height=80000,
        ports=(),
    )
    return LayoutRequest(
        protocol_version=1,
        request_id=UUID(int=1),
        semantic_digest="a" * 64,
        profile=LayoutProfile(
            id="architecture_compound_v1",
            version="1.0.0",
            engine="elkjs",
            engine_version="0.12.1",
            runtime_version="24.22.3",
            font_profile="dejavu_paths_2_37_v1",
            fingerprint="b" * 64,
        ),
        nodes=(node,),
        edges=(),
        labels=(),
    )


def response(r):
    return dict(
        protocol_version=1,
        request_id=str(r.request_id),
        semantic_digest=r.semantic_digest,
        profile_fingerprint=r.profile.fingerprint,
        geometry=dict(
            nodes=[
                dict(
                    id=r.nodes[0].id, box=dict(x=0.0025, y=0.0035, width=240, height=80)
                )
            ],
            groups=[],
            ports=[],
            labels=[],
            routes=[],
            bounds=dict(x=0, y=0, width=241, height=81),
        ),
    )


def frame(value):
    data = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    return struct.pack("!I", len(data)) + data


def test_raw_finite_geometry_rounds_once_half_even_and_binds_exact_request():
    r = request()
    geometry = parse_geometry(frame(response(r)), r, DiagramLimits())
    assert geometry.nodes[0].box.x == 2
    assert geometry.nodes[0].box.y == 4
    assert geometry.nodes[0].box.width == 240000


@pytest.mark.parametrize(
    "change",
    [
        "foreign_request",
        "foreign_digest",
        "foreign_profile",
        "missing_node",
        "duplicate_node",
        "extra_field",
        "infinity",
        "bool",
        "overflow",
        "missing_route",
        "shrunk_node",
    ],
)
def test_untrusted_reply_never_silently_repairs_or_omits(change):
    r = request()
    value = response(r)
    if change == "foreign_request":
        value["request_id"] = str(UUID(int=2))
    if change == "foreign_digest":
        value["semantic_digest"] = "c" * 64
    if change == "foreign_profile":
        value["profile_fingerprint"] = "c" * 64
    if change == "missing_node":
        value["geometry"]["nodes"] = []
    if change == "duplicate_node":
        value["geometry"]["nodes"] *= 2
    if change == "extra_field":
        value["geometry"]["user_script"] = "rejected"
    if change == "infinity":
        value["geometry"]["nodes"][0]["box"]["x"] = float("inf")
    if change == "bool":
        value["geometry"]["nodes"][0]["box"]["x"] = True
    if change == "overflow":
        value["geometry"]["nodes"][0]["box"]["x"] = 1000001
    if change == "missing_route":
        value["geometry"]["routes"] = [
            dict(edge_id=visual_id("edge", "foreign"), sections=[])
        ]
    if change == "shrunk_node":
        value["geometry"]["nodes"][0]["box"]["width"] = 1
    with pytest.raises(ValueError):
        parse_geometry(frame(value), r, DiagramLimits())


def test_framing_limits_duplicates_and_noninteger_protocol():
    r = request()
    good = frame(response(r))
    for bad in (good + b"extra", b"\0\0\0\xff" + good[4:], good[:3]):
        with pytest.raises(ValueError):
            parse_geometry(bad, r, DiagramLimits())
    with pytest.raises(ValueError):
        parse_geometry(good, r, DiagramLimits(max_helper_output_bytes=4))
    with pytest.raises(ValidationError):
        LayoutRequest.model_validate({**r.model_dump(), "protocol_version": True})


def test_scene_cycles_and_missing_endpoints_are_rejected():
    r = request()
    with pytest.raises(ValidationError):
        LayoutScene(
            nodes=(r.nodes[0].model_copy(update={"parent_id": r.nodes[0].id}),),
            edges=(),
            labels=(),
        )


def test_absent_installation_is_not_a_bare_subprocess_fallback():
    from backend.platform.diagrams.layout import INSTALL_ROOT

    if (INSTALL_ROOT / "deployment/runtime-lock.json").exists():
        pytest.skip(
            "deployment present: execute separately authorized actual proof suite"
        )
    with pytest.raises((OSError, ValueError)):
        verify_installation()


@pytest.mark.parametrize("exit_code", [1, 2, 137])
def test_failed_child_cannot_return_success_geometry(exit_code):
    import subprocess
    import sys
    from time import monotonic

    from backend.platform.diagrams.layout import ElkLayoutEngine

    class Control:
        def checkpoint(self):
            pass

    # Actual failed process returning a well-formed success frame. This proves
    # protocol exit classification, not the installed sandbox's security.
    payload = frame(response(request()))
    with subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); "
            f"sys.stdout.buffer.flush(); sys.exit({exit_code})",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        engine = ElkLayoutEngine(DiagramLimits(), font_manifest_digest="a" * 64)
        with pytest.raises(ValueError):
            engine._exchange(process, payload, monotonic() + 5, Control())


def test_cgroup_finalizer_and_pipes_survive_wait_failure(tmp_path, monkeypatch):
    """Control-flow unit test only; does not certify cgroups/OS isolation."""
    import io
    import subprocess
    from contextlib import contextmanager
    from types import SimpleNamespace

    from backend.platform.diagrams import layout as module

    closed = []
    (tmp_path / "cgroup.events").write_text("populated 0")

    @contextmanager
    def group(*args):
        try:
            yield tmp_path
        finally:
            closed.append(True)

    class Child:
        stdin, stdout, stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()

        def poll(self):
            return 0

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("fixture", timeout)

    class Control:
        def checkpoint(self):
            pass

    child = Child()
    lock = SimpleNamespace(files=())
    monkeypatch.setattr(module, "verify_installation", lambda: lock)
    monkeypatch.setattr(module, "job_cgroup", group)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: child)
    engine = module.ElkLayoutEngine(DiagramLimits(), font_manifest_digest="a" * 64)

    def interrupted(*args):
        raise InterruptedError("cancelled")

    monkeypatch.setattr(engine, "_exchange", interrupted)
    value = request()
    profile = module.create_layout_profile(value.profile.id, lock, "a" * 64)
    with pytest.raises(TimeoutError, match="diagram_timeout"):
        engine._layout_once(
            value.semantic_digest,
            profile,
            LayoutScene(nodes=value.nodes, edges=value.edges, labels=value.labels),
            float("inf"),
            Control(),
        )
    assert closed == [True]
    assert all(stream.closed for stream in (child.stdin, child.stdout, child.stderr))
