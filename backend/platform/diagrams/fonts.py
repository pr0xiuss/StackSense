"""Trusted bundled-font metrics and glyph paths; no user fonts or shaping."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from importlib.metadata import version
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from fontTools.pens.basePen import BasePen  # type: ignore[import-untyped]
from fontTools.ttLib import TTFont  # type: ignore[import-untyped]

from backend.platform.diagrams.contracts import (
    ClosedRecord,
    Glyph,
    GlyphPlacement,
    H,
    Id,
    N,
    PathCommand,
    Point,
)
from backend.platform.diagrams.model import canonical_bytes, visual_id

ASSETS = Path(__file__).parent / "assets" / "fonts"


class FontFile(ClosedRecord):
    name: Literal["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"]
    sha256: H
    size_bytes: N


class FontManifest(ClosedRecord):
    profile: Literal["dejavu_paths_2_37_v1"]
    family: Literal["DejaVu Sans"]
    release: Literal["2.37"]
    files: tuple[FontFile, FontFile]
    source_url: Literal[
        "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2"
    ]
    license_sha256: H
    tool: Literal["fonttools"]
    tool_version: Literal["4.68.0"]


@dataclass(frozen=True, slots=True)
class PreparedText:
    original_text: str
    display_text: str
    escaped: bool
    clipped: bool
    width: int
    glyphs: tuple[Glyph, ...]
    placements: tuple[GlyphPlacement, ...]


def _scaled(value: int | float, size: int, units: int) -> int:
    return int(
        (Decimal(str(value)) * size / units).quantize(
            Decimal(1), rounding=ROUND_HALF_EVEN
        )
    )


class _OutlinePen(BasePen):  # type: ignore[misc]
    """fontTools handles composite and multi-control-point TrueType contours."""

    def __init__(self, glyph_set: Any, size: int, units: int) -> None:
        super().__init__(glyph_set)
        self.commands: list[PathCommand] = []
        self.size, self.units = size, units

    def _emit(
        self, command: Literal["M", "L", "Q", "C", "Z"], points: tuple[Any, ...]
    ) -> None:
        operands = tuple(
            c
            for p in points
            for c in (
                _scaled(p[0], self.size, self.units),
                -_scaled(p[1], self.size, self.units),
            )
        )
        self.commands.append(PathCommand(command=command, operands=operands))

    def _moveTo(self, p: Any) -> None:
        self._emit("M", (p,))

    def _lineTo(self, p: Any) -> None:
        self._emit("L", (p,))

    def _qCurveToOne(self, p1: Any, p2: Any) -> None:
        self._emit("Q", (p1, p2))

    def _curveToOne(self, p1: Any, p2: Any, p3: Any) -> None:
        self._emit("C", (p1, p2, p3))

    def _closePath(self) -> None:
        self._emit("Z", ())

    def _endPath(self) -> None:
        raise ValueError("diagram_font_open_contour")


class DiagramFonts:
    def __init__(self) -> None:
        if version("fonttools") != "4.68.0":
            raise ValueError("diagram_runtime_unavailable")
        self.manifest = FontManifest.from_bytes(
            (ASSETS / "font-manifest.json").read_bytes(), max_bytes=8192
        )
        if tuple(f.name for f in self.manifest.files) != (
            "DejaVuSans-Bold.ttf",
            "DejaVuSans.ttf",
        ):
            raise ValueError("diagram_font_manifest_invalid")
        self.notice = (ASSETS / "LICENSE.dejavu.txt").read_text(encoding="utf-8")
        if (
            hashlib.sha256(self.notice.encode()).hexdigest()
            != self.manifest.license_sha256
        ):
            raise ValueError("diagram_font_notice_integrity")
        self._fonts: dict[str, Any] = {}
        self._hashes: dict[str, str] = {}
        for entry in self.manifest.files:
            path = ASSETS / entry.name
            content = path.read_bytes()
            if (
                len(content) != entry.size_bytes
                or hashlib.sha256(content).hexdigest() != entry.sha256
            ):
                raise ValueError("diagram_font_integrity")
            font = TTFont(
                BytesIO(content), lazy=False, recalcBBoxes=False, recalcTimestamp=False
            )
            if font["name"].getDebugName(5) != "Version 2.37":
                font.close()
                raise ValueError("diagram_font_version")
            style = "bold" if "Bold" in entry.name else "regular"
            self._fonts[style], self._hashes[style] = font, entry.sha256
            if any(ord(c) not in font.getBestCmap() for c in "[U+0123456789ABCDEF] "):
                self.close()
                raise ValueError("diagram_font_escape_glyph_unavailable")

    def close(self) -> None:
        for font in self._fonts.values():
            font.close()
        self._fonts.clear()

    def prepare(
        self, text: str, *, bold: bool = False, max_width: int = 240000
    ) -> PreparedText:
        if not 1 <= max_width <= 240000:
            raise ValueError("diagram_limit_exceeded")
        text.encode("utf-8", "strict")
        if len(text.encode()) > 4096:
            raise ValueError("diagram_limit_exceeded")
        style: Literal["regular", "bold"] = "bold" if bold else "regular"
        font, size = self._fonts[style], 12000 if bold else 14000
        cmap = font.getBestCmap()
        parts: list[str] = []
        escaped = False
        for c in text:
            n = ord(c)
            supported = 0x20 <= n <= 0x7E or 0xA0 <= n <= 0x24F or 0x370 <= n <= 0x52F
            if supported and c != "\\" and not unicodedata.combining(c) and n in cmap:
                parts.append(c)
            else:
                parts.append(f"[U+{n:04X}]" if n <= 0xFFFF else f"[U+{n:06X}]")
                escaped = True
        display = "".join(parts)
        clipped = len(display) > 96
        if clipped:
            display = display[:95] + ("…" if 0x2026 in cmap else ".")
        units = font["head"].unitsPerEm

        def width(value: str) -> int:
            return _scaled(
                sum(font["hmtx"].metrics[cmap[ord(c)]][0] for c in value), size, units
            )

        lines: list[str] = []
        rest = display
        for line_number in range(2):
            if not rest:
                break
            end = 0
            while end < len(rest) and width(rest[: end + 1]) <= max_width:
                end += 1
            if end == len(rest):
                lines.append(rest)
                rest = ""
                break
            if line_number == 0:
                space = rest.rfind(" ", 0, end + 1)
                cut = space if space > 0 else end
                lines.append(rest[:cut])
                rest = rest[cut:].lstrip(" ")
            else:
                clipped = True
                ellipsis = "…" if 0x2026 in cmap else "."
                while end > 0 and width(rest[:end] + ellipsis) > max_width:
                    end -= 1
                lines.append(rest[:end] + ellipsis)
        display = "\n".join(lines)
        if len(display) > 96:
            display = display[:95] + ("…" if 0x2026 in cmap else ".")
            clipped = True
        glyph_set = font.getGlyphSet()
        glyphs: dict[Id, Glyph] = {}
        placements: list[GlyphPlacement] = []
        advance_units = 0
        line = 0
        widest = 0
        for c in display:
            if c == "\n":
                widest = max(widest, _scaled(advance_units, size, units))
                advance_units = 0
                line += 1
                continue
            name = cmap[ord(c)]
            glyph_id = visual_id(
                "glyph", (self._hashes[style], style, font.getGlyphID(name), size)
            )
            pen = _OutlinePen(glyph_set, size, units)
            glyph_set[name].draw(pen)
            glyphs[glyph_id] = Glyph(
                id=glyph_id, font=style, commands=tuple(pen.commands)
            )
            placements.append(
                GlyphPlacement(
                    glyph_id=glyph_id,
                    origin=Point(x=_scaled(advance_units, size, units), y=line * 18000),
                )
            )
            advance_units += font["hmtx"].metrics[name][0]
        return PreparedText(
            text,
            display,
            escaped,
            clipped,
            max(widest, _scaled(advance_units, size, units)),
            tuple(glyphs[k] for k in sorted(glyphs)),
            tuple(placements),
        )

    def manifest_digest(self) -> str:
        return hashlib.sha256(canonical_bytes(self.manifest)).hexdigest()
