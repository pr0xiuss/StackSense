"""Deterministic prepared geometry and inert, font-independent SVG export."""

from __future__ import annotations

from collections.abc import Callable
from html import escape
from time import monotonic
from typing import Protocol

from backend.platform.delivery.contracts import ExecutionControl
from backend.platform.diagrams.builders import BuiltDiagram
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    Box,
    DiagramGroup,
    DiagramNode,
    DiagramSpec,
    Glyph,
    GlyphPlacement,
    LabelGeometry,
    LayoutProfile,
    LayoutSpec,
    Point,
    PreparedDiagram,
)
from backend.platform.diagrams.fonts import DiagramFonts, PreparedText
from backend.platform.diagrams.layout import (
    LayoutOutcome,
    LayoutScene,
    RuntimeEdge,
    RuntimeLabel,
    RuntimeNode,
)
from backend.platform.diagrams.model import canonical_bytes, digest, visual_id
from backend.platform.diagrams.validation import DiagramValidator


class LayoutEngine(Protocol):
    def layout(
        self,
        spec_digest: str,
        profile: LayoutProfile,
        scene: LayoutScene,
        deadline: float,
        control: ExecutionControl,
    ) -> LayoutOutcome: ...


def reuse_geometry(
    base: PreparedDiagram, built: BuiltDiagram, limits: DiagramLimits
) -> LayoutSpec | None:
    """Reuse a true subset only; ambiguous parent/edge/label mappings need ELK."""
    spec = built.spec
    if spec == base.spec:
        return base.layout
    if base.layout.ports:
        return None
    mapping: dict[str, str] = {}
    old_nodes = {n.entity.id: n for n in base.spec.nodes}
    for node in spec.nodes:
        old = old_nodes.get(node.entity.id)
        if old is None or (old.name, old.kind) != (node.name, node.kind):
            return None
        mapping[node.id] = old.id
    for group in spec.groups:
        candidates = [
            g
            for g in base.spec.groups
            if (g.kind, g.rule, g.container, g.label)
            == (group.kind, group.rule, group.container, group.label)
        ]
        if len(candidates) != 1:
            return None
        mapping[group.id] = candidates[0].id
    if len(set(mapping.values())) != len(mapping):
        return None
    old_sequence: tuple[DiagramNode | DiagramGroup, ...] = (
        *base.spec.nodes,
        *base.spec.groups,
    )
    new_sequence: tuple[DiagramNode | DiagramGroup, ...] = (*spec.nodes, *spec.groups)
    old_items = {n.id: n for n in old_sequence}
    for item in new_sequence:
        original = old_items[mapping[item.id]]
        parent = (
            item.parent_group_id if isinstance(item, DiagramGroup) else item.group_id
        )
        old_parent = (
            original.parent_group_id
            if isinstance(original, DiagramGroup)
            else original.group_id
        )
        if (mapping.get(parent) if parent else None) != old_parent:
            return None
    for edge in spec.edges:
        matching_edges = [
            e
            for e in base.spec.edges
            if e.members == edge.members
            and e.source_visual_id == mapping[edge.source_visual_id]
            and e.target_visual_id == mapping[edge.target_visual_id]
            and e.label == edge.label
        ]
        if len(matching_edges) != 1:
            return None
        mapping[edge.id] = matching_edges[0].id
    inverse = {old: new for new, old in mapping.items()}
    payload = base.layout.model_dump(mode="json", exclude={"layout_digest"})
    payload.update(diagram_id=spec.diagram_id, semantic_digest=spec.semantic_digest)
    for collection, key in (("nodes", "id"), ("groups", "id"), ("routes", "edge_id")):
        payload[collection] = [
            {**row, key: inverse[row[key]]}
            for row in payload[collection]
            if row[key] in inverse
        ]
    labels = []
    for row in payload["labels"]:
        old_owner = row["owner_id"]
        if old_owner not in inverse:
            continue
        role = next(
            (
                role
                for role in ("name", "kind", "relationship")
                if row["id"] == visual_id("label", (old_owner, role))
            ),
            None,
        )
        if role is None:
            return None
        owner = inverse[old_owner]
        labels.append(
            {**row, "id": visual_id("label", (owner, role)), "owner_id": owner}
        )
    payload["labels"] = labels
    if not spec.nodes and not spec.groups:
        payload.update(bounds=dict(x=0, y=0, width=0, height=0), glyphs=[], labels=[])
    payload["layout_digest"] = digest("ss.diagram.layout", payload)
    result = LayoutSpec.model_validate_json(canonical_bytes(payload))
    DiagramValidator(limits).layout(spec, result)
    return result


def prepare_layout(
    built: BuiltDiagram,
    fonts: DiagramFonts,
    engine: LayoutEngine,
    profile: LayoutProfile,
    limits: DiagramLimits,
    deadline: float,
    control: ExecutionControl,
) -> LayoutSpec:
    """Labels are measured before ELK; placement uses its exact returned boxes."""
    spec = built.spec
    DiagramValidator(limits).semantic(spec, built.catalog)
    texts: dict[str, tuple[str, PreparedText]] = {}
    roles: dict[str, str] = {}
    nodes: list[RuntimeNode] = []
    items: tuple[DiagramGroup | DiagramNode, ...] = (*spec.groups, *spec.nodes)
    for item in items:
        control.checkpoint()
        is_group = isinstance(item, DiagramGroup)
        text = fonts.prepare(
            item.label if isinstance(item, DiagramGroup) else item.name,
            bold=is_group,
            max_width=212000,
        )
        label_id = visual_id("label", (item.id, "name"))
        texts[label_id] = (item.id, text)
        roles[label_id] = "group" if is_group else "name"
        if isinstance(item, DiagramNode):
            kind_id = visual_id("label", (item.id, "kind"))
            texts[kind_id] = (
                item.id,
                fonts.prepare(item.kind.value, bold=True, max_width=212000),
            )
            roles[kind_id] = "kind"
        nodes.append(
            RuntimeNode(
                id=item.id,
                parent_id=(
                    item.parent_group_id
                    if isinstance(item, DiagramGroup)
                    else item.group_id
                ),
                width=240000,
                height=98000 if "\n" in text.display_text else 80000,
                ports=(),
            )
        )
    for edge in spec.edges:
        edge_label = visual_id("label", (edge.id, "relationship"))
        texts[edge_label] = (
            edge.id,
            fonts.prepare(edge.label, bold=True, max_width=212000),
        )
        roles[edge_label] = "edge"
    scene = LayoutScene(
        nodes=tuple(sorted(nodes, key=lambda n: n.id)),
        edges=tuple(
            RuntimeEdge(id=e.id, source=e.source_visual_id, target=e.target_visual_id)
            for e in spec.edges
        ),
        labels=tuple(
            RuntimeLabel(
                id=k,
                owner_id=owner,
                width=text.width,
                height=36000 if "\n" in text.display_text else 18000,
            )
            for k, (owner, text) in sorted(texts.items())
        ),
    )
    outcome = engine.layout(spec.semantic_digest, profile, scene, deadline, control)
    control.checkpoint()
    if monotonic() >= deadline:
        raise TimeoutError("diagram_timeout")
    glyphs: dict[str, Glyph] = {}
    labels: list[LabelGeometry] = []
    boxes = {p.id: p.box for p in (*outcome.geometry.nodes, *outcome.geometry.groups)}
    if set(texts) != {label.id for label in outcome.geometry.labels}:
        raise ValueError("diagram_integrity_error")
    for label in outcome.geometry.labels:
        owner, text = texts[label.id]
        if label.owner_id != owner:
            raise ValueError("diagram_integrity_error")
        box = label.box
        role = roles[label.id]
        if role != "edge":
            outer = boxes[owner]
            box = Box(
                x=outer.x + (24000 if role == "group" else 14000),
                y=outer.y + (32000 if role == "name" else 8000),
                width=text.width,
                height=36000 if "\n" in text.display_text else 18000,
            )
        glyphs.update((g.id, g) for g in text.glyphs)
        # Outlines use y-down coordinates and a baseline 14px below the box top.
        labels.append(
            LabelGeometry(
                id=label.id,
                owner_id=owner,
                box=box,
                display_text=text.display_text,
                original_text=text.original_text,
                glyphs=tuple(
                    GlyphPlacement(
                        glyph_id=p.glyph_id,
                        origin=Point(
                            x=box.x + p.origin.x,
                            y=box.y + 14000 + p.origin.y,
                        ),
                    )
                    for p in text.placements
                ),
                escaped=text.escaped,
                clipped=text.clipped,
            )
        )
    raw = dict(
        layout_schema_version="1.0.0",
        diagram_id=spec.diagram_id,
        semantic_digest=spec.semantic_digest,
        profile=outcome.profile,
        unit="milli_css_px",
        nodes=outcome.geometry.nodes,
        groups=outcome.geometry.groups,
        ports=outcome.geometry.ports,
        labels=tuple(sorted(labels, key=lambda label: label.id)),
        routes=outcome.geometry.routes,
        glyphs=tuple(glyphs[k] for k in sorted(glyphs)),
        font_notice=fonts.notice,
        bounds=outcome.geometry.bounds,
        fallback=outcome.fallback,
        limitations=tuple(
            sorted(
                {
                    reason
                    for label in labels
                    for reason, applies in (
                        ("unsupported_text_escaped", label.escaped),
                        ("label_limitation", label.clipped),
                    )
                    if applies
                }
            )
        ),
    )
    result = LayoutSpec.model_validate_json(
        canonical_bytes({**raw, "layout_digest": digest("ss.diagram.layout", raw)})
    )
    DiagramValidator(limits).layout(spec, result)
    return result


def svg_bytes(
    spec: DiagramSpec,
    layout: LayoutSpec,
    limits: DiagramLimits,
    checkpoint: Callable[[], None] = lambda: None,
) -> bytes:
    """No user SVG/XML, external references, font lookup, CSS or executable tags."""
    DiagramValidator(limits).layout(spec, layout)
    chunks: list[bytes] = []
    size = 0

    def emit(value: str) -> None:
        nonlocal size
        checkpoint()
        data = value.encode("utf-8")
        size += len(data)
        if size > limits.max_svg_bytes:
            raise ValueError("diagram_limit_exceeded")
        chunks.append(data)

    b = layout.bounds
    emit(
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
        f'viewBox="{b.x} {b.y} {max(b.width, 1)} {max(b.height, 1)}">'
    )
    emit(f"<title>{escape(spec.template.value)}</title>")
    emit(f"<metadata>{escape(layout.font_notice)}</metadata>")
    for item in (*layout.groups, *layout.nodes):
        box: Box = item.box
        emit(
            f'<rect x="{box.x}" y="{box.y}" width="{box.width}" '
            f'height="{box.height}" fill="#182330" stroke="#39bdf8" '
            'stroke-width="1000"/>'
        )
    for route in layout.routes:
        for section in route.sections:
            points = (section.start, *section.bends, section.end)
            path = "M " + " L ".join(f"{p.x} {p.y}" for p in points)
            emit(
                f'<path d="{path}" fill="none" stroke="#39bdf8" '
                'stroke-width="1000"/>'
            )
            # An inert arrowhead preserves static source-to-target direction.
            if len(points) >= 2:
                p, q = points[-2:]
                dx, dy = q.x - p.x, q.y - p.y
                scale = max(abs(dx), abs(dy), 1)
                ux, uy = dx * 6000 // scale, dy * 6000 // scale
                emit(
                    f'<path d="M {q.x-ux-uy//2} {q.y-uy+ux//2} '
                    f'L {q.x} {q.y} L {q.x-ux+uy//2} {q.y-uy-ux//2}" '
                    'fill="none" stroke="#39bdf8" stroke-width="1000"/>'
                )
    glyphs = {g.id: g for g in layout.glyphs}
    for label in layout.labels:
        # XML 1.0 disallows some canonical control characters even when escaped.
        original = "".join(
            (
                c
                if (
                    32 <= ord(c) <= 0xD7FF
                    or 0xE000 <= ord(c) <= 0xFFFD
                    or ord(c) >= 0x10000
                    or c in "\t\n\r"
                )
                else f"[U+{ord(c):04X}]"
            )
            for c in label.original_text
        )
        emit(f"<g><title>{escape(original)}</title>")
        for place in label.glyphs:
            commands = " ".join(
                c.command
                + (" " if c.operands else "")
                + " ".join(str(v) for v in c.operands)
                for c in glyphs[place.glyph_id].commands
            )
            emit(
                f'<path transform="translate({place.origin.x} {place.origin.y})" '
                f'd="{commands}" fill="#ecf5fc"/>'
            )
        emit("</g>")
    emit("</svg>")
    return b"".join(chunks)


def member_payloads(
    built: BuiltDiagram,
    layout: LayoutSpec,
    limits: DiagramLimits,
    checkpoint: Callable[[], None],
) -> dict[str, bytes]:
    DiagramValidator(limits).semantic(built.spec, built.catalog)
    result = {
        "spec": built.spec.to_bytes(),
        "layout": layout.to_bytes(),
        "members": built.catalog.to_bytes(),
        "svg": svg_bytes(built.spec, layout, limits, checkpoint),
    }
    for name, data in result.items():
        checkpoint()
        if len(data) > getattr(limits, f"max_{name}_bytes"):
            raise ValueError("diagram_limit_exceeded")
    if sum(map(len, result.values())) > limits.max_total_member_bytes:
        raise ValueError("diagram_limit_exceeded")
    return result
