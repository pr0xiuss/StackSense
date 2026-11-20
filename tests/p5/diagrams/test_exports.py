"""Prepared-vector unit tests; fake layout is not physical ELK certification."""

from time import monotonic
from xml.etree import ElementTree as ET

import pytest

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import Box, Point, PositionedBox
from backend.platform.diagrams.export import member_payloads, prepare_layout, svg_bytes
from backend.platform.diagrams.fonts import DiagramFonts
from backend.platform.diagrams.layout import (
    LayoutOutcome,
    RuntimeGeometry,
    RuntimeLabelBox,
)
from backend.platform.diagrams.validation import DiagramValidator
from tests.p5.diagrams.conftest import empty_parts
from tests.p5.diagrams.test_builders import build, monorepo


class Control:
    def checkpoint(self):
        pass

    def should_stop(self):
        return False


class UnitLayout:
    """Simple returned geometry to test font/export assembly, not ELK behavior."""

    def layout(self, spec_digest, profile, scene, deadline, control):
        boxes = {
            n.id: Box(x=0, y=i * 160000, width=300000, height=140000)
            for i, n in enumerate(scene.nodes)
        }
        label_boxes = {**boxes, **{e.id: boxes[e.source] for e in scene.edges}}
        parent_ids = {n.parent_id for n in scene.nodes}
        positions = tuple(PositionedBox(id=n.id, box=boxes[n.id]) for n in scene.nodes)
        from backend.platform.diagrams.contracts import EdgeRoute, RouteSection

        return LayoutOutcome(
            RuntimeGeometry(
                nodes=tuple(n for n in positions if n.id not in parent_ids),
                groups=tuple(n for n in positions if n.id in parent_ids),
                ports=(),
                labels=tuple(
                    RuntimeLabelBox(
                        id=label.id,
                        owner_id=label.owner_id,
                        box=Box(
                            x=14000,
                            y=label_boxes[label.owner_id].y + 14000,
                            width=label.width,
                            height=label.height,
                        ),
                    )
                    for label in scene.labels
                ),
                routes=tuple(
                    EdgeRoute(
                        edge_id=e.id,
                        sections=(
                            RouteSection(
                                start=Point(x=10000, y=boxes[e.source].y + 10000),
                                bends=(),
                                end=Point(x=10000, y=boxes[e.target].y + 10000),
                            ),
                        ),
                    )
                    for e in scene.edges
                ),
                bounds=Box(
                    x=0,
                    y=0,
                    width=300000 if scene.nodes else 0,
                    height=len(scene.nodes) * 160000 if scene.nodes else 0,
                ),
            ),
            profile,
            "none",
        )


@pytest.mark.parametrize("template", list(DiagramTemplate))
def test_all_four_exports_are_inert_deterministic_and_font_independent(template):
    built = build(monorepo(), template)
    profile = empty_parts(template)[2].profile
    fonts = DiagramFonts()
    try:
        layout = prepare_layout(
            built,
            fonts,
            UnitLayout(),
            profile,
            DiagramLimits(),
            monotonic() + 30,
            Control(),
        )
    finally:
        fonts.close()
    DiagramValidator(DiagramLimits()).layout(built.spec, layout)
    values = member_payloads(built, layout, DiagramLimits(), lambda: None)
    assert set(values) == {"spec", "layout", "members", "svg"}
    svg = values["svg"]
    assert svg == svg_bytes(built.spec, layout, DiagramLimits())
    root = ET.fromstring(svg)
    assert {x.tag.rsplit("}", 1)[-1] for x in root.iter()} <= {
        "svg",
        "rect",
        "path",
        "g",
        "title",
        "metadata",
    }
    assert all(
        not key.startswith("on") and "href" not in key
        for x in root.iter()
        for key in x.attrib
    )
    assert layout.glyphs and layout.labels
    assert all(
        p.glyph_id in {g.id for g in layout.glyphs}
        for label in layout.labels
        for p in label.glyphs
    )
    assert b"DejaVu" in svg


def test_svg_cap_and_cooperative_cancellation_are_not_silent():
    spec, _, layout = empty_parts()
    with pytest.raises(ValueError, match="diagram_limit_exceeded"):
        svg_bytes(spec, layout, DiagramLimits(max_svg_bytes=1))

    def stopped():
        raise InterruptedError("stopped")

    with pytest.raises(InterruptedError):
        svg_bytes(spec, layout, DiagramLimits(), stopped)


def test_padded_font_measurement_keeps_visible_escape_text_inside_node():
    fonts = DiagramFonts()
    try:
        value = fonts.prepare("<script>\x00\u202e" + "W" * 100, max_width=212000)
        assert value.width <= 212000
        assert value.escaped and value.clipped
        assert "[U+0000]" in value.display_text
    finally:
        fonts.close()
