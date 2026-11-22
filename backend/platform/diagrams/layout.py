"""Bounded B1 helper protocol and fail-closed installed sandbox execution.

No builder, publication, registry or bare-subprocess fallback lives here.
"""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import signal
import struct
import subprocess
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from time import monotonic
from typing import IO, Any, Literal, Protocol, Self, cast
from uuid import UUID, uuid4

from pydantic import model_validator

from backend.platform.delivery.contracts import ExecutionControl
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    Box,
    ClosedRecord,
    EdgeRoute,
    H,
    Id,
    LayoutProfile,
    N,
    Point,
    Port,
    PositionedBox,
)
from backend.platform.diagrams.linux_runtime import job_cgroup
from backend.platform.diagrams.model import canonical_bytes, digest

INSTALL_ROOT = Path("/opt/stacksense/diagram-artifacts")


class RuntimePort(ClosedRecord):
    id: Id
    side: Literal["NORTH", "SOUTH", "EAST", "WEST"]
    order: N


class RuntimeNode(ClosedRecord):
    id: Id
    parent_id: Id | None
    width: N
    height: N
    ports: tuple[RuntimePort, ...]


class RuntimeEdge(ClosedRecord):
    id: Id
    source: Id
    target: Id


class RuntimeLabel(ClosedRecord):
    id: Id
    owner_id: Id
    width: N
    height: N


class LayoutScene(ClosedRecord):
    nodes: tuple[RuntimeNode, ...]
    edges: tuple[RuntimeEdge, ...]
    labels: tuple[RuntimeLabel, ...]

    @model_validator(mode="after")
    def topology(self) -> Self:
        nodes = {n.id: n for n in self.nodes}
        edges = {e.id for e in self.edges}
        ids = [
            *(n.id for n in self.nodes),
            *(e.id for e in self.edges),
            *(label.id for label in self.labels),
            *(p.id for n in self.nodes for p in n.ports),
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("diagram_integrity_error")
        for n in self.nodes:
            if not (n.id.startswith("dn:") or n.id.startswith("dg:")):
                raise ValueError("diagram_input_invalid")
            if not n.width or not n.height or max(n.width, n.height) > 10**9:
                raise ValueError("diagram_input_invalid")
            chain = {n.id}
            parent = n.parent_id
            if parent is not None and not parent.startswith("dg:"):
                raise ValueError("diagram_input_invalid")
            while parent is not None:
                if parent not in nodes or parent in chain:
                    raise ValueError("diagram_input_invalid")
                chain.add(parent)
                parent = nodes[parent].parent_id
        if any(e.source not in nodes or e.target not in nodes for e in self.edges):
            raise ValueError("diagram_input_invalid")
        if any(
            label.owner_id not in nodes and label.owner_id not in edges
            for label in self.labels
        ):
            raise ValueError("diagram_input_invalid")
        return self


class LayoutRequest(LayoutScene):
    protocol_version: Literal[1]
    request_id: UUID
    semantic_digest: H
    profile: LayoutProfile


class RuntimeLabelBox(ClosedRecord):
    id: Id
    owner_id: Id
    box: Box


class RuntimeGeometry(ClosedRecord):
    nodes: tuple[PositionedBox, ...]
    groups: tuple[PositionedBox, ...]
    ports: tuple[Port, ...]
    labels: tuple[RuntimeLabelBox, ...]
    routes: tuple[EdgeRoute, ...]
    bounds: Box


class LockedFile(ClosedRecord):
    path: str
    sha256: H


class RuntimeLock(ClosedRecord):
    version: Literal["1.0.0"]
    node: Literal["24.22.3"]
    bubblewrap: Literal["0.12.0"]
    elkjs: Literal["0.12.1"]
    files: tuple[LockedFile, ...]


class RuntimeAssetLock(Protocol):
    @property
    def files(self) -> tuple[LockedFile, ...]: ...


class LayoutGeometryFailure(ValueError):
    """A bound helper's geometry/layout failure, not corruption/isolation loss."""


@dataclass(frozen=True, slots=True)
class LayoutOutcome:
    geometry: RuntimeGeometry
    profile: LayoutProfile
    fallback: Literal["none", "simple_layered"]


def verify_installation() -> RuntimeLock:
    """A lock proves installation integrity, never B1 security acceptance."""
    if sys.platform != "linux" or not hasattr(os, "geteuid"):
        raise ValueError("diagram_runtime_unavailable")
    if os.geteuid() == 0:
        raise ValueError("diagram_runtime_unavailable")
    lock_path = INSTALL_ROOT / "deployment" / "runtime-lock.json"
    for path in (lock_path, *lock_path.parents):
        s = path.lstat()
        if path.is_symlink() or s.st_uid != 0 or s.st_mode & 0o022:
            raise ValueError("diagram_runtime_unavailable")
    lock = RuntimeLock.from_bytes(lock_path.read_bytes(), max_bytes=65536)
    if not lock.files or len({f.path for f in lock.files}) != len(lock.files):
        raise ValueError("diagram_runtime_unavailable")
    paths = {f.path for f in lock.files}
    if (
        not {
            "bin/bwrap",
            "runtime/root/bin/node",
            "runtime/root/app/elk_layout.mjs",
            "runtime/root/app/node_modules/elkjs/lib/elk.bundled.js",
            "layout_runtime/launch_elk.py",
            "layout_runtime/seccomp_policy.json",
        }
        <= paths
    ):
        raise ValueError("diagram_runtime_unavailable")
    for entry in lock.files:
        relative = Path(entry.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("diagram_runtime_unavailable")
        path = INSTALL_ROOT / relative
        for parent in (path, *path.parents):
            if parent == INSTALL_ROOT.parent:
                break
            s = parent.lstat()
            if parent.is_symlink() or s.st_uid != 0 or s.st_mode & 0o022:
                raise ValueError("diagram_runtime_unavailable")
        value = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                value.update(chunk)
        if value.hexdigest() != entry.sha256:
            raise ValueError("diagram_runtime_unavailable")
    actual: set[str] = set()
    for root in (
        INSTALL_ROOT / "bin",
        INSTALL_ROOT / "layout_runtime",
        INSTALL_ROOT / "runtime/root",
    ):
        for path in root.rglob("*"):
            info = path.lstat()
            if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError("diagram_runtime_unavailable")
            if path.is_file():
                actual.add(str(path.relative_to(INSTALL_ROOT)))
            if len(actual) > len(paths):
                raise ValueError("diagram_runtime_unavailable")
    if actual != paths:
        raise ValueError("diagram_runtime_unavailable")
    return lock


def create_layout_profile(
    profile_id: str, runtime_lock: RuntimeAssetLock, font_manifest_digest: str
) -> LayoutProfile:
    """The profile hashes actual runtime/font identities, never a guessed label."""
    payload = dict(
        id=profile_id,
        version="1.0.0",
        engine="elkjs",
        engine_version="0.12.1",
        runtime_version="24.22.3",
        font_profile="dejavu_paths_2_37_v1",
    )
    options = {
        "algorithm": "layered",
        "direction": "DOWN",
        "seed": 42,
        "routing": "POLYLINE" if profile_id == "simple_layered_v1" else "ORTHOGONAL",
        "hierarchy": "INCLUDE_CHILDREN",
        "node_spacing": 40000,
        "layer_spacing": 60000,
        "group_padding": 24000,
        "group_header": 24000,
        "node_width": 240000,
        "node_height": 80000,
        "max_node_height": 116000,
        "line_height": 18000,
        "shelf_width": 1600000,
        "gutter": 80000,
    }
    fingerprint = digest(
        "ss.diagram.profile",
        (
            payload,
            options,
            tuple(sorted((f.path, f.sha256) for f in runtime_lock.files)),
            font_manifest_digest,
        ),
    )
    return LayoutProfile.model_validate({**payload, "fingerprint": fingerprint})


def parse_geometry(
    data: bytes, request: LayoutRequest, limits: DiagramLimits
) -> RuntimeGeometry:
    """Independently bind reply and round finite raw px exactly once to milli-px."""
    if len(data) < 4 or len(data) > limits.max_helper_output_bytes + 4:
        raise ValueError("diagram_limit_exceeded")
    if struct.unpack("!I", data[:4])[0] != len(data) - 4:
        raise ValueError("diagram_integrity_error")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("diagram_integrity_error")
            result[key] = value
        return result

    def invalid(value: str) -> Any:
        raise ValueError("diagram_integrity_error")

    raw = json.loads(
        data[4:].decode("utf-8", "strict"),
        object_pairs_hook=pairs,
        parse_float=Decimal,
        parse_constant=invalid,
    )
    if (
        not isinstance(raw, dict)
        or type(raw.get("protocol_version")) is not int
        or raw.get("protocol_version") != 1
        or raw.get("request_id") != str(request.request_id)
    ):
        raise ValueError("diagram_integrity_error")
    if "error" in raw:
        if set(raw) != {"protocol_version", "request_id", "error"} or raw[
            "error"
        ] not in ("invalid_input", "capacity", "layout_failed"):
            raise ValueError("diagram_integrity_error")
        if raw["error"] == "layout_failed":
            raise LayoutGeometryFailure("diagram_integrity_error")
        raise ValueError(
            "diagram_limit_exceeded"
            if raw["error"] == "capacity"
            else "diagram_integrity_error"
        )
    if (
        set(raw)
        != {
            "protocol_version",
            "request_id",
            "semantic_digest",
            "profile_fingerprint",
            "geometry",
        }
        or raw["semantic_digest"] != request.semantic_digest
        or raw["profile_fingerprint"] != request.profile.fingerprint
    ):
        raise ValueError("diagram_integrity_error")

    def convert(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: coordinate(v) if k in ("x", "y", "width", "height") else convert(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [convert(v) for v in value]
        return value

    def coordinate(value: Any) -> int:
        if (
            type(value) not in (int, Decimal)
            or not Decimal(value).is_finite()
            or abs(value) > 1000000
        ):
            raise ValueError("diagram_integrity_error")
        return int(
            (Decimal(value) * 1000).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
        )

    geometry = RuntimeGeometry.model_validate_json(
        canonical_bytes(convert(raw["geometry"]))
    )
    expected = (
        (
            {n.id for n in request.nodes if not n.id.startswith("dg:")},
            [n.id for n in geometry.nodes],
        ),
        (
            {n.id for n in request.nodes if n.id.startswith("dg:")},
            [n.id for n in geometry.groups],
        ),
        ({e.id for e in request.edges}, [r.edge_id for r in geometry.routes]),
        (
            {label.id for label in request.labels},
            [label.id for label in geometry.labels],
        ),
        (
            (
                set()
                if request.profile.id == "simple_layered_v1"
                else {p.id for n in request.nodes for p in n.ports}
            ),
            [p.id for p in geometry.ports],
        ),
    )
    for ids, actual in expected:
        if ids != set(actual) or len(set(actual)) != len(actual):
            raise ValueError("diagram_integrity_error")
    if sum(len(r.sections) for r in geometry.routes) > limits.max_route_sections:
        raise ValueError("diagram_limit_exceeded")
    boxes = {n.id: n.box for n in (*geometry.nodes, *geometry.groups)}
    outer = geometry.bounds

    def inside(point: Point, box: Box) -> bool:
        return (
            box.x <= point.x <= box.x + box.width
            and box.y <= point.y <= box.y + box.height
        )

    for node in (*geometry.nodes, *geometry.groups):
        box = node.box
        if (
            box.width <= 0
            or box.height <= 0
            or not inside(Point(x=box.x, y=box.y), outer)
            or not inside(Point(x=box.x + box.width, y=box.y + box.height), outer)
        ):
            raise ValueError("diagram_integrity_error")
    inputs = {node.id: node for node in request.nodes}
    for node in (*geometry.nodes, *geometry.groups):
        original = inputs[node.id]
        if node.box.width < original.width or node.box.height < original.height:
            raise ValueError("diagram_integrity_error")
        if original.parent_id is not None:
            parent = boxes[original.parent_id]
            if (
                node.box.x < parent.x + 24000
                or node.box.y < parent.y + 48000
                or node.box.x + node.box.width > parent.x + parent.width - 24000
                or node.box.y + node.box.height > parent.y + parent.height - 24000
            ):
                raise LayoutGeometryFailure("diagram_integrity_error")
    owners = {p.id: n.id for n in request.nodes for p in n.ports}
    if any(
        p.owner_id != owners[p.id] or not inside(p.point, boxes[p.owner_id])
        for p in geometry.ports
    ):
        raise ValueError("diagram_integrity_error")
    labels = {label.id: label.owner_id for label in request.labels}
    if any(label.owner_id != labels[label.id] for label in geometry.labels):
        raise ValueError("diagram_integrity_error")
    label_inputs = {label.id: label for label in request.labels}
    for label in geometry.labels:
        box, label_input = label.box, label_inputs[label.id]
        if (
            box.width != label_input.width
            or box.height != label_input.height
            or not inside(Point(x=box.x, y=box.y), outer)
            or not inside(Point(x=box.x + box.width, y=box.y + box.height), outer)
        ):
            raise LayoutGeometryFailure("diagram_integrity_error")
    edges = {edge.id: edge for edge in request.edges}
    for route in geometry.routes:
        edge = edges[route.edge_id]
        if not inside(route.sections[0].start, boxes[edge.source]) or not inside(
            route.sections[-1].end, boxes[edge.target]
        ):
            raise ValueError("diagram_integrity_error")
        if any(
            left.end != right.start
            for left, right in zip(route.sections, route.sections[1:], strict=False)
        ):
            raise LayoutGeometryFailure("diagram_integrity_error")
        for section in route.sections:
            if any(
                not inside(point, outer)
                for point in (section.start, *section.bends, section.end)
            ):
                raise ValueError("diagram_integrity_error")
    return geometry


class ElkLayoutEngine:
    def __init__(self, limits: DiagramLimits, *, font_manifest_digest: str) -> None:
        if len(font_manifest_digest) != 64 or any(
            c not in "0123456789abcdef" for c in font_manifest_digest
        ):
            raise ValueError("diagram_runtime_unavailable")
        self.limits = limits
        self.font_manifest_digest = font_manifest_digest

    def layout(
        self,
        spec_digest: str,
        profile: LayoutProfile,
        scene: LayoutScene,
        deadline: float,
        control: ExecutionControl,
    ) -> LayoutOutcome:
        deadline = min(deadline, monotonic() + self.limits.helper_wall_seconds)
        try:
            result = self._layout_once(spec_digest, profile, scene, deadline, control)
            return LayoutOutcome(result, profile, "none")
        except LayoutGeometryFailure:
            control.checkpoint()
            if profile.id == "simple_layered_v1" or monotonic() >= deadline:
                raise
            fallback = create_layout_profile(
                "simple_layered_v1", verify_installation(), self.font_manifest_digest
            )
            result = self._layout_once(spec_digest, fallback, scene, deadline, control)
            return LayoutOutcome(result, fallback, "simple_layered")

    def _layout_once(
        self,
        spec_digest: str,
        profile: LayoutProfile,
        scene: LayoutScene,
        deadline: float,
        control: ExecutionControl,
    ) -> RuntimeGeometry:
        control.checkpoint()
        if monotonic() >= deadline:
            raise TimeoutError("diagram_timeout")
        lock = verify_installation()
        if profile != create_layout_profile(
            profile.id, lock, self.font_manifest_digest
        ):
            raise ValueError("diagram_integrity_error")
        scene = LayoutScene.model_validate(scene)
        if (
            sum(n.id.startswith("dn:") for n in scene.nodes) > self.limits.max_nodes
            or sum(n.id.startswith("dg:") for n in scene.nodes) > self.limits.max_groups
            or len(scene.edges) > self.limits.max_edges
        ):
            raise ValueError("diagram_limit_exceeded")
        request = LayoutRequest(
            protocol_version=1,
            request_id=uuid4(),
            semantic_digest=spec_digest,
            profile=profile,
            **scene.model_dump(),
        )
        payload = request.to_bytes()
        if len(payload) > self.limits.max_helper_input_bytes:
            raise ValueError("diagram_limit_exceeded")
        if monotonic() >= deadline:
            raise TimeoutError("diagram_timeout")
        cgroup = job_cgroup(request.request_id, self.limits)
        group = cgroup.__enter__()
        process: subprocess.Popen[bytes] | None = None
        try:
            command = [
                sys.executable,
                "-I",
                str(INSTALL_ROOT / "layout_runtime" / "launch_elk.py"),
                str(request.request_id),
                str(self.limits.max_helper_memory_bytes),
                str(self.limits.max_helper_processes),
                str(self.limits.max_helper_fds),
                str(self.limits.max_helper_cpu_seconds),
                str(self.limits.max_scratch_bytes),
                str(self.limits.max_total_member_bytes),
            ]
            process = subprocess.Popen(
                command,
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
            output = self._exchange(
                process, struct.pack("!I", len(payload)) + payload, deadline, control
            )
            geometry = parse_geometry(output, request, self.limits)
            control.checkpoint()
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")
            return geometry
        finally:
            try:
                if process is not None:
                    try:
                        if (
                            process.poll() is None
                            or (group / "cgroup.events").read_text().find("populated 1")
                            >= 0
                        ):
                            (group / "cgroup.kill").write_text("1")
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            raise TimeoutError("diagram_timeout") from None
                    finally:
                        for stream in (process.stdin, process.stdout, process.stderr):
                            if stream is not None:
                                stream.close()
            finally:
                # A failed wait/pipe cleanup must not bypass the cgroup's own
                # kill-and-reap cleanup (including timeout/error paths).
                cgroup.__exit__(None, None, None)

    def _exchange(
        self,
        process: subprocess.Popen[bytes],
        payload: bytes,
        deadline: float,
        control: ExecutionControl,
    ) -> bytes:
        assert (
            process.stdin is not None
            and process.stdout is not None
            and process.stderr is not None
        )
        output, error = bytearray(), bytearray()
        remaining = memoryview(payload)
        with selectors.DefaultSelector() as selector:
            for stream, events in (
                (process.stdin, selectors.EVENT_WRITE),
                (process.stdout, selectors.EVENT_READ),
                (process.stderr, selectors.EVENT_READ),
            ):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, events)
            while selector.get_map():
                control.checkpoint()
                if monotonic() >= deadline:
                    raise TimeoutError("diagram_timeout")
                for key, _ in selector.select(min(0.1, max(0, deadline - monotonic()))):
                    stream = cast(IO[bytes], key.fileobj)
                    if stream is process.stdin:
                        try:
                            count = os.write(stream.fileno(), remaining[:65536])
                        except BrokenPipeError:
                            count = len(remaining)
                        remaining = remaining[count:]
                        if not remaining:
                            selector.unregister(stream)
                            stream.close()
                    else:
                        chunk = os.read(stream.fileno(), 65536)
                        target = output if stream is process.stdout else error
                        target.extend(chunk)
                        cap = (
                            self.limits.max_helper_output_bytes + 4
                            if stream is process.stdout
                            else self.limits.max_helper_stderr_bytes
                        )
                        if len(target) > cap:
                            raise ValueError("diagram_limit_exceeded")
                        if not chunk:
                            selector.unregister(stream)
                if process.poll() is not None and not selector.get_map():
                    break
        try:
            process.wait(timeout=max(0.001, min(2, deadline - monotonic())))
        except subprocess.TimeoutExpired:
            raise TimeoutError("diagram_timeout") from None
        control.checkpoint()
        if monotonic() >= deadline:
            raise TimeoutError("diagram_timeout")
        if process.returncode == 78:
            raise ValueError("diagram_runtime_unavailable")
        if process.returncode is not None and (
            process.returncode < 0 or process.returncode >= 128
        ):
            raise ValueError("diagram_limit_exceeded")
        if process.returncode != 0:
            # A helper may report a typed failure with exit 1. Never accept a
            # successful-looking frame (or partial pressure output) from a
            # failed process. parse_geometry still independently binds errors.
            try:
                if (
                    process.returncode != 1
                    or len(output) < 4
                    or struct.unpack("!I", output[:4])[0] != len(output) - 4
                ):
                    raise ValueError
                failure = json.loads(output[4:])
                if (
                    not isinstance(failure, dict)
                    or set(failure) != {"protocol_version", "request_id", "error"}
                    or failure["error"]
                    not in ("invalid_input", "capacity", "layout_failed")
                ):
                    raise ValueError
            except ValueError, UnicodeError:
                raise ValueError("diagram_runtime_unavailable") from None
        return bytes(output)
