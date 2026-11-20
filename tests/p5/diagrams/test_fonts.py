"""Actual approved font bytes/toolchain; not ELK or physical-store proof."""

import hashlib
from importlib.metadata import version

import pytest

from backend.platform.diagrams.fonts import ASSETS, DiagramFonts
from backend.platform.diagrams.model import canonical_bytes


@pytest.fixture
def fonts():
    value = DiagramFonts()
    try:
        yield value
    finally:
        value.close()


def test_exact_assets_and_tool_are_acquired_and_reproducible(fonts):
    assert version("fonttools") == "4.68.0"
    for file in fonts.manifest.files:
        data = (ASSETS / file.name).read_bytes()
        assert len(data) == file.size_bytes
        assert hashlib.sha256(data).hexdigest() == file.sha256
    assert "Bitstream" in fonts.notice and "Tavmjong Bah" in fonts.notice


@pytest.mark.parametrize(
    "text",
    [
        "Hello",
        "Αρχιτεκτονική",
        "Сервис",
        "é",
        "e\u0301",
        "\ufeffA\r\n",
        "数据库",
        "👩‍💻",
        "\u202ehello",
        "\\",
    ],
)
def test_metrics_and_paths_repeat_exactly_without_host_fonts(fonts, text):
    first = fonts.prepare(text)
    second = fonts.prepare(text)
    assert first == second
    assert first.original_text == text
    assert tuple(canonical_bytes(g) for g in first.glyphs) == tuple(
        canonical_bytes(g) for g in second.glyphs
    )
    assert first.width >= 0


@pytest.mark.parametrize(
    "text,marker",
    [
        ("数据库", "[U+6570]"),
        ("😀", "[U+01F600]"),
        ("\ufeff", "[U+FEFF]"),
        ("e\u0301", "[U+0301]"),
        ("\r\n", "[U+000D][U+000A]"),
    ],
)
def test_unsupported_text_is_explicit_not_dropped(fonts, text, marker):
    prepared = fonts.prepare(text)
    assert prepared.escaped
    assert marker in prepared.display_text


def test_long_and_invalid_labels(fonts):
    prepared = fonts.prepare("W" * 200)
    assert prepared.clipped and len(prepared.display_text) <= 96
    assert prepared.original_text == "W" * 200
    assert prepared.width <= 240000
    assert prepared.display_text.count("\n") <= 1
    assert max((g.origin.y for g in prepared.placements), default=0) <= 18000
    with pytest.raises(UnicodeError):
        fonts.prepare("\ud800")
    with pytest.raises(ValueError):
        fonts.prepare("x" * 4097)
