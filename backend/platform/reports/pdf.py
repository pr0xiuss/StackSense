"""Provider-free PDF rendering of validated C4 and unchanged C2 vectors."""

from __future__ import annotations

import hashlib
import io
import unicodedata
from collections import Counter
from time import monotonic
from typing import Any
from xml.sax.saxutils import escape

from pypdf import PdfReader
from pypdf.generic import ContentStream, IndirectObject, StreamObject
from reportlab.lib.pagesizes import A4, landscape  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]
from reportlab.platypus import Paragraph  # type: ignore[import-untyped]

from backend.platform.delivery.contracts import ExecutionControl
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import (
    CoverageSection,
    DiagnosticsSection,
    DiagramsSection,
    InventorySection,
    PreparedReport,
    ProvenanceSection,
    RenderedReport,
    ReportContractError,
    ReportSourceRef,
    ReportSpec,
)
from backend.platform.reports.validation import ReportValidator


def register_dejavu_fonts(assets: tuple[tuple[str, str, bytes], ...]) -> None:
    expected = {
        "DejaVuSans.ttf": (
            "7da195a74c55bef988d0d48f9508bd5d849425c1770dba5d7bfc6ce9ed848954"
        ),
        "DejaVuSans-Bold.ttf": (
            "e6476c1b80502924294eed40894c5b18e06c181444ca953e5334262df9c27724"
        ),
    }
    if {name: sha for name, sha, _ in assets} != expected:
        raise ReportContractError("report_font_integrity")
    for name, sha, data in sorted(assets):
        if hashlib.sha256(data).hexdigest() != sha:
            raise ReportContractError("report_font_integrity")
        font_name = "DejaVuSans-Bold" if "Bold" in name else "DejaVuSans"
        # Register from the exact pinned bytes; never fall back to a host font.
        pdfmetrics.registerFont(TTFont(font_name, io.BytesIO(data)))


class DeterministicCanvas(canvas.Canvas):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.update(invariant=1, pageCompression=1)
        super().__init__(*args, **kwargs)


class ReportLabPdfRenderer:
    def __init__(self, limits: ReportLimits | None = None) -> None:
        self.limits = limits or ReportLimits()

    def render(
        self,
        prepared: PreparedReport,
        deadline: float,
        control: ExecutionControl | None = None,
    ) -> RenderedReport:
        def checkpoint() -> None:
            if control:
                control.checkpoint()
            if monotonic() >= deadline:
                raise TimeoutError("report_timeout")

        checkpoint()
        prepared = PreparedReport.model_validate(prepared)
        spec = ReportSpec.model_validate(prepared.spec)
        ReportValidator(self.limits).validate(spec)
        register_dejavu_fonts(prepared.font_assets)
        out = io.BytesIO()
        c = DeterministicCanvas(out, pagesize=A4)
        c.setTitle("StackSense Architecture Analysis Report")
        c.setAuthor("StackSense")
        c.setSubject("C4:" + spec.report_spec_digest)
        style = ParagraphStyle(
            "body",
            fontName="DejaVuSans",
            fontSize=9,
            leading=12,
            splitLongWords=True,
            spaceAfter=6,
        )
        y = A4[1] - 36
        page_count = 1

        def text(value: object) -> str:
            raw = str(value)
            if len(raw.encode("utf-8")) > self.limits.max_text_field_bytes:
                raise ReportContractError("report_limit_exceeded")
            cmap = pdfmetrics.getFont("DejaVuSans").face.charWidths
            displayed = []
            for char in raw:
                n = ord(char)
                supported = (
                    (32 <= n <= 0x24F or 0x300 <= n <= 0x52F)
                    and n in cmap
                    and unicodedata.bidirectional(char)
                    not in {
                        "R",
                        "AL",
                        "RLE",
                        "RLO",
                        "LRE",
                        "LRO",
                        "PDF",
                        "RLI",
                        "LRI",
                        "FSI",
                        "PDI",
                    }
                )
                displayed.append(
                    char if supported or char in "\n\t" else f"[U+{n:04X}]"
                )
            return (
                escape("".join(displayed)).replace("\n", "<br/>").replace("\t", "    ")
            )

        def new_page(size: tuple[float, float] = A4) -> None:
            nonlocal y, page_count
            checkpoint()
            c.setFont("DejaVuSans", 8)
            c.drawString(36, 20, f"StackSense | {page_count}")
            c.showPage()
            page_count += 1
            if page_count > self.limits.max_pdf_pages:
                raise ReportContractError("report_limit_exceeded")
            c.setPageSize(size)
            y = size[1] - 36

        def paragraph(value: object, heading: bool = False) -> None:
            nonlocal y
            checkpoint()
            s = (
                ParagraphStyle(
                    "heading",
                    parent=style,
                    fontName="DejaVuSans-Bold",
                    fontSize=14,
                    leading=18,
                )
                if heading
                else style
            )
            pending = [Paragraph(text(value), s)]
            while pending:
                checkpoint()
                p = pending.pop(0)
                _, h = p.wrap(A4[0] - 72, A4[1] - 72)
                if h > y - 36:
                    parts = p.split(A4[0] - 72, max(0, y - 36))
                    if not parts:
                        new_page()
                        pending.insert(0, p)
                        continue
                    first, *rest = parts
                    _, used = first.wrap(A4[0] - 72, y - 36)
                    first.drawOn(c, 36, y - used)
                    new_page()
                    pending = rest + pending
                else:
                    p.drawOn(c, 36, y - h)
                    y -= h + 6

        def section(title: str, key: str, first: bool = False) -> None:
            if not first:
                new_page()
            c.bookmarkPage(key)
            c.addOutlineEntry(title, key, level=0)
            paragraph(title, True)

        def fields(value: Any) -> str:
            def compact(item: Any) -> str:
                if isinstance(item, tuple):
                    return " / ".join(compact(value) for value in item)
                if isinstance(item, dict):
                    return ", ".join(
                        f"{key.replace('_', ' ')}={compact(value)}"
                        for key, value in item.items()
                    )
                return str(item)

            return "; ".join(
                f"{key.replace('_', ' ')}: {compact(item)}"
                for key, item in value.model_dump(
                    mode="python", exclude_none=True
                ).items()
            )

        def source_ref(value: ReportSourceRef) -> str:
            data = value.model_dump(mode="python", exclude_none=True)
            location = data.get("path", "not recorded")
            if data.get("line") is not None:
                location += f":{data['line']}"
            parts = [
                str(data.get("source_kind", "source")),
                str(data.get("source_record_type", "record")),
            ]
            if data.get("logical_id"):
                parts.append(f"logical ID {data['logical_id']}")
            if data.get("source_fact_key"):
                parts.append(f"fact {data['source_fact_key']}")
            parts.append(f"location {location}")
            return " | ".join(parts)

        def counts(values: tuple[tuple[str, int], ...]) -> str:
            return "; ".join(f"{kind}: {count}" for kind, count in values)

        section("StackSense Architecture Analysis Report", "metadata", True)
        paragraph(
            "Deterministic static report — not runtime verification "
            "or a security assessment."
        )
        paragraph(f"Report ID: {spec.metadata.report_id}")
        paragraph(f"Captured at: {spec.metadata.captured_at.isoformat()}")
        paragraph(
            "Repository display: "
            + (
                f"{spec.metadata.project_name or 'unavailable'} / "
                f"{spec.metadata.repository_name or 'unavailable'}"
                if spec.metadata.display_names_available
                else "unavailable in the immutable source snapshot"
            )
        )
        paragraph(f"Revision: {spec.metadata.revision_sha or 'unavailable'}")
        paragraph(f"Source snapshot digest: {spec.metadata.source_snapshot_digest}")
        paragraph("Exact source scope", True)
        for key, value in spec.metadata.scope.model_dump(mode="python").items():
            paragraph(f"{key.replace('_',' ')}: {value}")
        paragraph("Producer profile: " + fields(spec.metadata.profile.profile))
        section("1. Architecture Inventory & Boundaries", "inventory")
        inv = next(s for s in spec.sections if isinstance(s, InventorySection))
        paragraph(f"Counts by kind: {counts(inv.counts_by_kind)}")
        paragraph(f"Counts by status: {counts(inv.counts_by_status)}")
        paragraph(
            "Relationship counts by kind: " + counts(inv.relationship_counts_by_kind)
        )
        paragraph(f"Selected: {inv.selected_count}; omitted: {inv.omitted_count}")
        for ref in (*inv.selected_entities, *inv.selected_relationships):
            paragraph(source_ref(ref))
        diagrams = next(s for s in spec.sections if isinstance(s, DiagramsSection))
        inputs = {d.template: d for d in spec.diagram_inputs}
        pages = sorted({p.page_index for p in diagrams.placements})
        for index in pages:
            placements = [p for p in diagrams.placements if p.page_index == index]
            size = landscape(A4) if placements[0].slot_id == "full_landscape" else A4
            new_page(size)
            if index == pages[0]:
                c.bookmarkPage("diagrams")
                c.addOutlineEntry("2. Architecture Diagrams", "diagrams", level=0)
            c.setFont("DejaVuSans-Bold", 12)
            c.drawString(36, size[1] - 30, "2. Architecture Diagrams")
            for p in placements:
                checkpoint()
                d = inputs[p.template]
                x0, y0, x1, y1 = (v / 1000 for v in p.clip_rect)
                c.setFont("DejaVuSans", 8)
                title = p.caption + (
                    f" — tile {p.tile_row},{p.tile_column}"
                    if p.tile_row is not None
                    else ""
                )
                c.drawString(x0, y1 + 10, title)
                c.saveState()
                clip = c.beginPath()
                clip.rect(x0, y0, x1 - x0, y1 - y0)
                c.clipPath(clip, stroke=0)
                scale = p.scale_numerator / p.scale_denominator / 1000
                c.transform(
                    scale,
                    0,
                    0,
                    -scale,
                    p.translation_mpt_x / 1000,
                    y1 + (p.translation_mpt_y - p.clip_rect[1]) / 1000,
                )
                c.addLiteral(f"/SS_{d.template.value} BMC")
                self._draw_vectors(c, d.prepared_diagram.layout, checkpoint)
                c.addLiteral("EMC")
                c.restoreState()
                caption = Paragraph(
                    text(
                        f"View: {d.coverage.view_state}; exact generation: "
                        f"{d.receipt.accepted.reference.generation_id}"
                    ),
                    ParagraphStyle(
                        "caption", fontName="DejaVuSans", fontSize=7, leading=9
                    ),
                )
                _, caption_height = caption.wrap(x1 - x0, 50)
                caption.drawOn(c, x0, y0 - 8 - caption_height)
        section("3. Authoritative Analysis Diagnostics", "diagnostics")
        ds = next(s for s in spec.sections if isinstance(s, DiagnosticsSection))
        if not ds.diagnostics:
            paragraph(ds.empty_disclaimer)
        for diagnostic in ds.diagnostics:
            paragraph(
                f"{diagnostic.severity.upper()} | {diagnostic.code} | "
                f"{diagnostic.stage}",
                False,
            )
            paragraph(
                diagnostic.message
                if diagnostic.withheld_reason is None
                else f"Message withheld: {diagnostic.withheld_reason}"
            )
            paragraph(
                f"ID {diagnostic.diagnostic_id} | "
                f"category {diagnostic.category} | scope {diagnostic.scope}"
            )
            paragraph(
                f"Created {diagnostic.created_at.isoformat()} | "
                f"retryability {diagnostic.retryability}"
            )
            paragraph("Source: " + source_ref(diagnostic.source_ref))
            for evidence in diagnostic.evidence_refs:
                paragraph("Evidence: " + source_ref(evidence))
        section("4. Coverage, Uncertainty & Limitations", "coverage")
        cv = next(s for s in spec.sections if isinstance(s, CoverageSection))
        paragraph(f"Entities: {cv.coverage.total_entities}")
        paragraph(f"Relationships: {cv.coverage.total_relationships}")
        paragraph(f"Evidence records: {cv.coverage.total_evidence}")
        paragraph(f"Unresolved findings: {cv.coverage.total_unresolved}")
        paragraph(f"Conflicts: {cv.coverage.total_conflicts}")
        paragraph(f"Analysis status: {cv.coverage.analysis_status}")
        if cv.coverage.persisted_coverage is not None:
            persisted = cv.coverage.persisted_coverage
            paragraph(
                "File coverage: "
                f"analyzed {persisted.analyzed_files_count}; "
                f"unsupported {persisted.unsupported_files_count}; "
                f"failed {persisted.failed_files_count}; "
                f"excluded {persisted.excluded_files_count}; "
                f"partial {persisted.is_partial}"
            )
        paragraph(
            "Report selection: "
            f"inventory {cv.coverage.selected_inventory_count} selected / "
            f"{cv.coverage.omitted_inventory_count} omitted; "
            f"diagnostics {cv.coverage.selected_diagnostic_count} selected / "
            f"{cv.coverage.omitted_diagnostic_count} omitted; "
            f"source references {cv.coverage.selected_reference_count} selected / "
            f"{cv.coverage.omitted_reference_count} omitted."
        )
        if cv.coverage.limitation_codes:
            paragraph(
                "Recorded limitations: " + ", ".join(cv.coverage.limitation_codes)
            )
        paragraph(
            "UNKNOWN and unavailable values are not zero or complete. "
            "Findings retain canonical uncertainty and conflict; static source "
            "references do not prove runtime behavior."
        )
        paragraph(
            "Unsupported glyphs/scripts are visibly escaped as [U+XXXX]; "
            "original Unicode remains in the immutable specification."
        )
        for d in spec.diagram_inputs:
            paragraph(d.template.value, True)
            paragraph(
                f"View {d.coverage.view_state}; "
                f"source partial {d.coverage.source_partial}; "
                f"selection bounded {d.coverage.selection_bounded}; "
                f"scan exhausted {d.coverage.scan_exhausted}"
            )
            paragraph("Source completeness: " + fields(d.coverage.source_completeness))
            for count in d.coverage.counts:
                paragraph(fields(count))
            paragraph("Coverage reasons: " + ", ".join(d.coverage.reasons))
            for item in d.prepared_diagram.spec.legend:
                paragraph("Legend: " + fields(item))
            for limitation in d.prepared_diagram.layout.limitations:
                paragraph(limitation)
        section("5. Provenance, Licenses & Appendix", "provenance")
        pr = next(s for s in spec.sections if isinstance(s, ProvenanceSection))
        paragraph("Report spec digest: " + spec.report_spec_digest)
        paragraph("Source snapshot digest: " + pr.source_snapshot_digest)
        paragraph("Selection policy: " + pr.selection_policy)
        paragraph("Font licenses: " + ", ".join(pr.font_licenses))
        for receipt in pr.diagram_receipts:
            diagram_ref = receipt.accepted.reference
            paragraph(str(diagram_ref.binding.slot.template), True)
            paragraph(
                f"Receipt: {receipt.receipt_id}; same exact source scope as the "
                "cover (validated)"
            )
            for key in (
                "resource_id",
                "generation_id",
                "artifact_id",
                "candidate_id",
                "input_fingerprint",
                "size_bytes",
            ):
                paragraph(f"{key.replace('_',' ')}: {getattr(diagram_ref,key)}")
            paragraph("Digests: " + fields(diagram_ref.digests))
            paragraph("Profile: " + fields(diagram_ref.binding.profile))
        for provenance_ref in pr.source_refs:
            paragraph(source_ref(provenance_ref))
        paragraph("Bundled font-license notice digest", True)
        paragraph(
            "The immutable C4 input records the complete bundled license notice. "
            "Its SHA-256 is "
            + hashlib.sha256(pr.font_license_notice.encode("utf-8")).hexdigest()
            + "."
        )
        c.setFont("DejaVuSans", 8)
        c.drawString(36, 20, f"StackSense | {page_count}")
        checkpoint()
        c.save()
        data = out.getvalue()
        checkpoint()
        pages_count = self._validate_rendered_pdf(data, spec)
        return RenderedReport(
            pdf_bytes=data,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            page_count=pages_count,
            report_spec_digest=spec.report_spec_digest,
            renderer_profile_digest=prepared.renderer_profile_digest,
            validation_version="1.0.0",
        )

    @staticmethod
    def _draw_vectors(c: Any, layout: Any, checkpoint: Any) -> None:
        c.setLineWidth(1000)
        for item in (*layout.groups, *layout.nodes):
            checkpoint()
            b = item.box
            c.setFillColorRGB(0.94, 0.97, 0.99)
            c.setStrokeColorRGB(0.1, 0.3, 0.45)
            c.rect(b.x, b.y, b.width, b.height, stroke=1, fill=1)
        c.setStrokeColorRGB(0.1, 0.4, 0.65)
        for route in layout.routes:
            checkpoint()
            for s in route.sections:
                points = (s.start, *s.bends, s.end)
                path = c.beginPath()
                path.moveTo(points[0].x, points[0].y)
                for p in points[1:]:
                    path.lineTo(p.x, p.y)
                c.drawPath(path, stroke=1, fill=0)
                p, q = points[-2:]
                dx, dy = q.x - p.x, q.y - p.y
                scale = max(abs(dx), abs(dy), 1)
                ux, uy = dx * 6000 // scale, dy * 6000 // scale
                path = c.beginPath()
                path.moveTo(q.x - ux - uy // 2, q.y - uy + ux // 2)
                path.lineTo(q.x, q.y)
                path.lineTo(q.x - ux + uy // 2, q.y - uy - ux // 2)
                c.drawPath(path, stroke=1, fill=0)
        glyphs = {g.id: g for g in layout.glyphs}
        c.setFillColorRGB(0.05, 0.08, 0.12)
        for label in layout.labels:
            checkpoint()
            for place in label.glyphs:
                c.saveState()
                c.translate(place.origin.x, place.origin.y)
                path = c.beginPath()
                current = (0.0, 0.0)
                for command in glyphs[place.glyph_id].commands:
                    o = command.operands
                    if command.command == "M":
                        path.moveTo(*o)
                        current = (float(o[0]), float(o[1]))
                    elif command.command == "L":
                        path.lineTo(*o)
                        current = (float(o[0]), float(o[1]))
                    elif command.command == "C":
                        path.curveTo(*o)
                        current = (float(o[-2]), float(o[-1]))
                    elif command.command == "Q":
                        x, y = current
                        cx, cy, ex, ey = o
                        path.curveTo(
                            x + 2 * (cx - x) / 3,
                            y + 2 * (cy - y) / 3,
                            ex + 2 * (cx - ex) / 3,
                            ey + 2 * (cy - ey) / 3,
                            ex,
                            ey,
                        )
                        current = (float(ex), float(ey))
                    else:
                        path.close()
                c.drawPath(path, stroke=0, fill=1)
                c.restoreState()

    def _validate_rendered_pdf(self, pdf_bytes: bytes, spec: ReportSpec) -> int:
        if len(pdf_bytes) > self.limits.max_pdf_bytes:
            raise ReportContractError("report_limit_exceeded")
        if not pdf_bytes.startswith(b"%PDF-") or b"%%EOF" not in pdf_bytes[-1024:]:
            raise ReportContractError("report_integrity_error")
        reader = PdfReader(io.BytesIO(pdf_bytes), strict=True)
        if (
            reader.is_encrypted
            or not 1 <= len(reader.pages) <= self.limits.max_pdf_pages
        ):
            raise ReportContractError("report_integrity_error")
        forbidden = {
            "/JavaScript",
            "/JS",
            "/OpenAction",
            "/AA",
            "/EmbeddedFiles",
            "/Filespec",
            "/URI",
            "/Launch",
            "/GoToR",
            "/RichMedia",
            "/XFA",
        }
        seen: set[tuple[int, int]] = set()
        visited = stream_bytes = 0

        def visit(value: Any) -> None:
            nonlocal visited, stream_bytes
            visited += 1
            if visited > 200000:
                raise ReportContractError("report_limit_exceeded")
            if isinstance(value, IndirectObject):
                key = (value.idnum, value.generation)
                if key in seen:
                    return
                seen.add(key)
                visit(value.get_object())
                return
            if isinstance(value, dict):
                if (
                    forbidden.intersection(str(k) for k in value)
                    or str(value.get("/S")) in forbidden
                ):
                    raise ReportContractError("report_integrity_error")
                if isinstance(value, StreamObject):
                    stream_bytes += len(value.get_data())
                    if stream_bytes > self.limits.max_staged_bytes:
                        raise ReportContractError("report_limit_exceeded")
                for child in value.values():
                    visit(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    visit(child)

        visit(reader.trailer)
        if (
            reader.metadata is None
            or reader.metadata.get("/Subject") != "C4:" + spec.report_spec_digest
        ):
            raise ReportContractError("report_integrity_error")
        for page in reader.pages:
            dims = sorted(
                (round(float(page.mediabox.width)), round(float(page.mediabox.height)))
            )
            if dims != sorted(round(v) for v in A4):
                raise ReportContractError("report_integrity_error")
        expected = {
            "/SS_" + d.template.value: d.prepared_diagram.layout
            for d in spec.diagram_inputs
        }
        observed: Counter[str] = Counter()
        section = spec.sections[2]
        assert isinstance(section, DiagramsSection)
        wanted = Counter("/SS_" + p.template.value for p in section.placements)
        for page in reader.pages:
            current: str | None = None
            operators: Counter[bytes] = Counter()
            rectangles: list[tuple[int, ...]] = []
            for operands, operator in ContentStream(
                page.get_contents(), reader
            ).operations:
                if operator == b"BMC":
                    current = str(operands[0])
                    operators = Counter()
                    rectangles = []
                elif operator == b"EMC" and current is not None:
                    if current not in expected:
                        raise ReportContractError("report_integrity_error")
                    layout = expected[current]
                    boxes = [
                        (n.box.x, n.box.y, n.box.width, n.box.height)
                        for n in (*layout.groups, *layout.nodes)
                    ]
                    if rectangles != boxes:
                        raise ReportContractError("report vector rectangle mismatch")
                    wanted_ops: Counter[bytes] = Counter()
                    for route in layout.routes:
                        for route_section in route.sections:
                            wanted_ops[b"m"] += 2
                            wanted_ops[b"l"] += len(route_section.bends) + 3
                    glyphs = {g.id: g for g in layout.glyphs}
                    for label in layout.labels:
                        for place in label.glyphs:
                            for command in glyphs[place.glyph_id].commands:
                                wanted_ops[
                                    {
                                        "M": b"m",
                                        "L": b"l",
                                        "Q": b"c",
                                        "C": b"c",
                                        "Z": b"h",
                                    }[command.command]
                                ] += 1
                    if any(operators[op] != count for op, count in wanted_ops.items()):
                        raise ReportContractError("report vector path mismatch")
                    observed[current] += 1
                    current = None
                elif current is not None:
                    operators[operator] += 1
                    if operator == b"re":
                        rectangles.append(tuple(int(v) for v in operands))
        if observed != wanted:
            raise ReportContractError("report four-diagram embedding mismatch")
        return len(reader.pages)
