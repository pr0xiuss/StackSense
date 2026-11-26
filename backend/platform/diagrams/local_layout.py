"""Development-only, unpublished ELK layout; never registered as a sealed artifact.

Unlike the production runner this executes Node as the current user without a
filesystem or network sandbox. Only use with trusted local repositories.
"""

from __future__ import annotations

import hashlib
import shutil
import struct
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.delivery.contracts import DiagramTemplate, ExecutionControl
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import DiagramSpec, LayoutProfile, LayoutSpec
from backend.platform.diagrams.layout import (
    LayoutOutcome,
    LayoutRequest,
    LayoutScene,
    parse_geometry,
)

# Local process-only cache. Access is checked by the API before every lookup;
# entries are never accepted generations and disappear on process restart.
_CACHE: OrderedDict[
    tuple[str, str, str, str, str], tuple[DiagramSpec, LayoutSpec, bytes, int]
] = OrderedDict()
_CACHE_LOCK = Lock()
_CACHE_MAX_BYTES = 32 * 1024 * 1024


def render_local_diagram(
    record: ArchitectureVersionResponse, template: DiagramTemplate, database_url: str
) -> tuple[DiagramSpec, LayoutSpec, bytes]:
    """Build transient spec, layout and SVG from the exact published version."""
    from backend.platform.diagrams.builders import build_from_source
    from backend.platform.diagrams.export import prepare_layout, svg_bytes
    from backend.platform.diagrams.fonts import DiagramFonts
    from backend.platform.diagrams.layout import LockedFile, create_layout_profile
    from backend.platform.diagrams.query import SourceBudget, canonical_read_source
    from backend.platform.diagrams.service import canonical_scope

    class Control:
        def checkpoint(self) -> None:
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")

        def should_stop(self) -> bool:
            return monotonic() >= deadline

    key = (
        hashlib.sha256(database_url.encode()).hexdigest(),
        str(record.project_id),
        str(record.id),
        record.content_digest,
        template.value,
    )
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            _CACHE.move_to_end(key)
            return cached[0], cached[1], cached[2]
    limits = DiagramLimits()
    deadline = monotonic() + limits.build_seconds
    control = Control()
    budget = SourceBudget(limits, deadline, control.checkpoint)
    with canonical_read_source(database_url, budget) as source:
        built = build_from_source(source, canonical_scope(record), template, budget)
    root = Path(__file__).parent / "layout_runtime"
    node = shutil.which("node")
    if node is None:
        raise ValueError("diagram_runtime_unavailable")
    paths = {
        "node": Path(node),
        "helper": root / "local_elk_layout.mjs",
        "elk": root / "node_modules/elkjs/lib/elk.bundled.js",
    }
    lock = SimpleNamespace(
        files=tuple(
            LockedFile(path=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for name, path in sorted(paths.items())
        )
    )
    profile_name = {
        "system_overview": "architecture_compound_v1",
        "component_architecture": "architecture_compound_v1",
        "dependency_map": "dependency_layered_v1",
        "data_flow": "static_flow_v1",
    }[template.value]
    fonts = DiagramFonts()
    try:
        profile = create_layout_profile(profile_name, lock, fonts.manifest_digest())
        layout = prepare_layout(
            built, fonts, LocalLayoutEngine(limits), profile, limits, deadline, control
        )
        svg = svg_bytes(built.spec, layout, limits, control.checkpoint)
        size = len(built.spec.to_bytes()) + len(layout.to_bytes()) + len(svg)
        if size <= _CACHE_MAX_BYTES:
            with _CACHE_LOCK:
                _CACHE[key] = (built.spec, layout, svg, size)
                _CACHE.move_to_end(key)
                while sum(item[3] for item in _CACHE.values()) > _CACHE_MAX_BYTES:
                    _CACHE.popitem(last=False)
        return built.spec, layout, svg
    finally:
        fonts.close()


def render_local_svg(
    record: ArchitectureVersionResponse, template: DiagramTemplate, database_url: str
) -> bytes:
    """Return the SVG portion of a local, unpublished diagram."""
    return render_local_diagram(record, template, database_url)[2]


class LocalLayoutEngine:
    """Run the existing bounded protocol without claiming production isolation."""

    def __init__(self, limits: DiagramLimits) -> None:
        self.limits = limits

    def layout(
        self,
        spec_digest: str,
        profile: LayoutProfile,
        scene: LayoutScene,
        deadline: float,
        control: ExecutionControl,
    ) -> LayoutOutcome:
        control.checkpoint()
        node = shutil.which("node")
        helper = Path(__file__).parent / "layout_runtime" / "local_elk_layout.mjs"
        if node is None or not helper.is_file():
            raise ValueError("diagram_runtime_unavailable")
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
        timeout = min(self.limits.helper_wall_seconds, deadline - monotonic())
        if timeout <= 0:
            raise TimeoutError("diagram_timeout")
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            try:
                result = subprocess.run(
                    [node, str(helper)],
                    input=struct.pack("!I", len(payload)) + payload,
                    stdout=output,
                    stderr=errors,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("diagram_timeout") from exc
            control.checkpoint()
            if result.returncode != 0:
                raise ValueError("diagram_runtime_unavailable")
            output.seek(0)
            data = output.read(self.limits.max_helper_output_bytes + 5)
        return LayoutOutcome(
            parse_geometry(data, request, self.limits), profile, "none"
        )
