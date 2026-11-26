"""Real Node/ELK local-development layout, not a production sandbox proof."""

import hashlib
from time import monotonic
from uuid import uuid4

import pytest

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.diagrams import local_layout
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.export import prepare_layout, svg_bytes
from backend.platform.diagrams.fonts import DiagramFonts
from backend.platform.diagrams.local_layout import LocalLayoutEngine
from tests.p5.diagrams.conftest import empty_parts
from tests.p5.diagrams.test_api import record_for
from tests.p5.diagrams.test_builders import build, monorepo
from tests.p5.diagrams.test_c2_consumers import prepared
from tests.p5.diagrams.test_exports import Control


@pytest.mark.parametrize("template", list(DiagramTemplate))
def test_local_layout_builds_real_template_svg(template):
    limits = DiagramLimits()
    built = build(monorepo(), template)
    fonts = DiagramFonts()
    try:
        layout = prepare_layout(
            built,
            fonts,
            LocalLayoutEngine(limits),
            empty_parts(template)[2].profile,
            limits,
            monotonic() + 30,
            Control(),
        )
        assert svg_bytes(built.spec, layout, limits).startswith(b"<svg ")
    finally:
        fonts.close()


def test_cache_is_scoped_by_project_version_digest_and_template(monkeypatch):
    value = prepared(DiagramTemplate.OVERVIEW)
    record = record_for(value)
    key = (
        hashlib.sha256(b"not-used").hexdigest(),
        str(record.project_id),
        str(record.id),
        record.content_digest,
        "system_overview",
    )
    monkeypatch.setattr(
        local_layout,
        "_CACHE",
        local_layout.OrderedDict(
            {
                key: (value.spec, value.layout, b"<svg/>", 6),
            }
        ),
    )
    spec, layout, svg = local_layout.render_local_diagram(
        record, DiagramTemplate.OVERVIEW, "not-used"
    )
    assert (spec, layout, svg) == (value.spec, value.layout, b"<svg/>")

    from backend.platform.diagrams import query

    def reject_miss(*args, **kwargs):
        raise RuntimeError("cache miss")

    monkeypatch.setattr(query, "canonical_read_source", reject_miss)
    with pytest.raises(RuntimeError, match="cache miss"):
        local_layout.render_local_diagram(
            record.model_copy(update={"content_digest": "0" * 64}),
            DiagramTemplate.OVERVIEW,
            "not-used",
        )
    with pytest.raises(RuntimeError, match="cache miss"):
        local_layout.render_local_diagram(
            record, DiagramTemplate.DEPENDENCY, "not-used"
        )
    with pytest.raises(RuntimeError, match="cache miss"):
        local_layout.render_local_diagram(record, DiagramTemplate.OVERVIEW, "other-db")
    for changed in (
        record.model_copy(update={"project_id": uuid4()}),
        record.model_copy(update={"id": uuid4()}),
    ):
        with pytest.raises(RuntimeError, match="cache miss"):
            local_layout.render_local_diagram(
                changed, DiagramTemplate.OVERVIEW, "not-used"
            )
