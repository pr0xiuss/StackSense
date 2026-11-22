"""Deterministic PDF rendering engine for Architecture Analysis Report.

Uses ReportLab 5.1.0 and pypdf 7.1.1.
"""

from __future__ import annotations

import hashlib
import io
from time import monotonic
from typing import Any

from pypdf import PdfReader
from reportlab.graphics.shapes import (  # type: ignore[import-untyped]
    Drawing,
    Group,
    Line,
    Rect,
    String,
)
from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import (  # type: ignore[import-untyped]
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.platform.delivery.contracts import ExecutionControl
from backend.platform.reports.contracts import (
    CoverageSection,
    DiagnosticsSection,
    DiagramsSection,
    InventorySection,
    PreparedReport,
    ProvenanceSection,
    RenderedReport,
    ReportContractError,
    ReportDiagramInput,
    ReportDiagramPlacement,
    ReportSpec,
)


class DeterministicCanvas(canvas.Canvas):  # type: ignore[misc]
    """Canvas enforcing invariant mode and fixed dates for byte-level determinism."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 0
        super().__init__(*args, **kwargs)


_FONTS_REGISTERED = False


def register_dejavu_fonts(font_assets: tuple[tuple[str, str, bytes], ...]) -> None:
    """Register DejaVu font family into ReportLab pdfmetrics."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    registered_names = set(pdfmetrics.getRegisteredFontNames())
    for filename, _sha256, data in font_assets:
        font_name = "DejaVuSans-Bold" if "Bold" in filename else "DejaVuSans"
        if font_name not in registered_names:
            try:
                font = TTFont(font_name, io.BytesIO(data))
                pdfmetrics.registerFont(font)
                registered_names.add(font_name)
            except Exception:
                # Fallback to Helvetica if font parsing fails
                pass
    _FONTS_REGISTERED = True


def _safe_font(preferred: str, fallback: str = "Helvetica") -> str:
    if preferred in pdfmetrics.getRegisteredFontNames():
        return preferred
    return fallback


class ReportLabPdfRenderer:
    """Deterministic, provider-free ReportLab PDF renderer and pypdf validator."""

    def __init__(self) -> None:
        pass

    def render(
        self,
        prepared: PreparedReport,
        deadline: float,
        control: ExecutionControl | None = None,
    ) -> RenderedReport:
        """Render prepared report into deterministic validated PDF bytes."""
        if monotonic() >= deadline:
            raise TimeoutError("report_render_timeout")
        if control:
            control.checkpoint()

        register_dejavu_fonts(prepared.font_assets)
        font_body = _safe_font("DejaVuSans", "Helvetica")
        font_bold = _safe_font("DejaVuSans-Bold", "Helvetica-Bold")

        spec = prepared.spec
        buffer = io.BytesIO()

        # Page geometry: A4 (595.27 x 841.89 points) with 36pt margins
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
            title="Architecture Analysis Report",
            author="StackSense Platform",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName=font_bold,
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1A202C"),
            alignment=0,
        )
        h1_style = ParagraphStyle(
            "ReportH1",
            parent=styles["Heading1"],
            fontName=font_bold,
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
        )
        h2_style = ParagraphStyle(
            "ReportH2",
            parent=styles["Heading2"],
            fontName=font_bold,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#4A5568"),
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True,
        )
        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["Normal"],
            fontName=font_body,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#2D3748"),
        )
        caption_style = ParagraphStyle(
            "ReportCaption",
            parent=styles["Italic"],
            fontName=font_body,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#718096"),
            alignment=1,
        )

        story: list[Any] = []

        # ==========================================
        # SECTION 1: METADATA & COVER
        # ==========================================
        story.append(Paragraph("StackSense Architecture Analysis Report", title_style))
        story.append(Spacer(1, 10))
        story.append(
            Paragraph(
                f"Report Type: <b>{spec.metadata.report_type}</b> &nbsp;|&nbsp; "
                f"Schema: <b>C4 v{spec.metadata.c4_version}</b> &nbsp;|&nbsp; "
                f"Mode: <b>{spec.metadata.deterministic_mode}</b>",
                body_style,
            )
        )
        story.append(Spacer(1, 15))

        scope = spec.metadata.scope
        meta_table_data = [
            ["Report ID", str(spec.metadata.report_id)],
            ["Architecture Version ID", str(scope.architecture_version_id)],
            ["Analysis ID", str(scope.analysis_id)],
            ["Project ID", str(scope.project_id)],
            ["Repository ID", str(scope.repository_id)],
            [
                "Captured At (UTC)",
                spec.metadata.captured_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            ],
            [
                "Canonical Model Digest",
                scope.canonical_digest[:16] + "..." + scope.canonical_digest[-16:],
            ],
            [
                "Snapshot Digest",
                spec.metadata.source_snapshot_digest[:16]
                + "..."
                + spec.metadata.source_snapshot_digest[-16:],
            ],
            ["Renderer Profile", f"{prepared.renderer_profile_digest[:16]}..."],
        ]
        meta_table = Table(
            [
                [
                    Paragraph(f"<b>{c[0]}</b>", body_style),
                    Paragraph(str(c[1]), body_style),
                ]
                for c in meta_table_data
            ],
            colWidths=[180, 343],
        )
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 20))

        # ==========================================
        # SECTION 2: INVENTORY & BOUNDARIES
        # ==========================================
        story.append(PageBreak())
        story.append(Paragraph("1. Architecture Inventory & Boundaries", h1_style))
        story.append(Spacer(1, 8))

        inv_sec = next(s for s in spec.sections if isinstance(s, InventorySection))
        story.append(Paragraph("<b>Canonical Entities by Kind:</b>", h2_style))
        if inv_sec.counts_by_kind:
            kind_table_data = [["Kind", "Count"]] + [
                [k, str(v)] for k, v in inv_sec.counts_by_kind
            ]
            t = Table(kind_table_data, colWidths=[260, 263])
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                        ("FONTNAME", (0, 0), (-1, 0), font_bold),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(t)
        else:
            story.append(
                Paragraph("<i>No canonical entities recorded.</i>", body_style)
            )
        story.append(Spacer(1, 10))

        story.append(
            Paragraph("<b>Selected Boundary Architecture Elements:</b>", h2_style)
        )
        if inv_sec.selected_entities:
            ent_rows = [["Logical Identifier", "Kind"]] + [
                [e.logical_id or str(e.artifact_id), e.source_record_type or "entity"]
                for e in inv_sec.selected_entities[:15]
            ]
            t_ent = Table(ent_rows, colWidths=[380, 143])
            t_ent.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                        ("FONTNAME", (0, 0), (-1, 0), font_bold),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(t_ent)
        else:
            story.append(Paragraph("<i>No boundary entities selected.</i>", body_style))
        story.append(Spacer(1, 10))

        # ==========================================
        # SECTION 3: ARCHITECTURE DIAGRAMS
        # ==========================================
        story.append(PageBreak())
        story.append(
            Paragraph("2. Architecture Diagrams (Option 3 Embedded)", h1_style)
        )
        story.append(Spacer(1, 8))

        diag_sec = next(s for s in spec.sections if isinstance(s, DiagramsSection))
        diagram_inputs_map = {d.template: d for d in diag_sec.diagram_inputs}

        for placement in diag_sec.placements:
            if control:
                control.checkpoint()
            diag_input = diagram_inputs_map.get(placement.template)
            if diag_input:
                d_drawing = self._render_diagram_drawing(
                    diag_input, placement, font_body, font_bold
                )
                story.append(d_drawing)
                story.append(Spacer(1, 4))
                story.append(Paragraph(placement.caption, caption_style))
                story.append(Spacer(1, 14))

        # ==========================================
        # SECTION 4: AUTHORITATIVE DIAGNOSTICS
        # ==========================================
        story.append(PageBreak())
        story.append(Paragraph("3. Authoritative Analysis Diagnostics", h1_style))
        story.append(Spacer(1, 8))

        diag_sec_record = next(
            s for s in spec.sections if isinstance(s, DiagnosticsSection)
        )
        if diag_sec_record.diagnostics:
            diag_rows = [["Severity", "Code", "Stage", "Path / Scope", "Message"]]
            for d in diag_sec_record.diagnostics[:30]:
                msg = d.message[:80] + "..." if len(d.message) > 80 else d.message
                loc = d.path or d.scope
                diag_rows.append(
                    [
                        d.severity.upper(),
                        d.code,
                        d.stage,
                        loc or "-",
                        msg,
                    ]
                )
            t_diag = Table(
                [[Paragraph(c, body_style) for c in row] for row in diag_rows],
                colWidths=[65, 95, 75, 110, 178],
            )
            t_diag.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                        ("FONTNAME", (0, 0), (-1, 0), font_bold),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(t_diag)
        else:
            story.append(Paragraph(diag_sec_record.empty_disclaimer, body_style))
        story.append(Spacer(1, 15))

        # ==========================================
        # SECTION 5: COVERAGE & LIMITATIONS
        # ==========================================
        story.append(PageBreak())
        story.append(Paragraph("4. Coverage, Uncertainty & Limitations", h1_style))
        story.append(Spacer(1, 8))

        cov_sec = next(s for s in spec.sections if isinstance(s, CoverageSection))
        cov = cov_sec.coverage
        cov_data = [
            ["Metric", "Value"],
            ["Total Canonical Entities", str(cov.total_entities)],
            ["Total Canonical Relationships", str(cov.total_relationships)],
            ["Total Evidence Records", str(cov.total_evidence)],
            ["Unresolved References", str(cov.total_unresolved)],
            ["Model Conflicts", str(cov.total_conflicts)],
            ["Analysis Status", cov.analysis_status],
            ["Selected Inventory Count", str(cov.selected_inventory_count)],
            ["Omitted Inventory Count", str(cov.omitted_inventory_count)],
            ["Authoritative Diagnostics Total", str(cov.selected_diagnostic_count)],
        ]
        t_cov = Table(cov_data, colWidths=[260, 263])
        t_cov.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(t_cov)
        story.append(Spacer(1, 12))
        story.append(
            Paragraph(
                "<b>Operational Limitations:</b><br/>"
                "• Deterministic static inspection: facts represent verified "
                "source-code structure without runtime profiling.<br/>"
                "• Strict four-diagram barrier: report incorporates immutable "
                "diagram generations pinned at barrier time.<br/>"
                "• Security boundary: source credentials and raw host paths "
                "are redacted from export representations.",
                body_style,
            )
        )
        story.append(Spacer(1, 15))

        # ==========================================
        # SECTION 6: PROVENANCE & APPENDIX
        # ==========================================
        story.append(PageBreak())
        story.append(Paragraph("5. Provenance, Licenses & Appendix", h1_style))
        story.append(Spacer(1, 8))

        prov_sec = next(s for s in spec.sections if isinstance(s, ProvenanceSection))
        prov_data = [
            ["Item", "Details"],
            ["Report Spec Digest", spec.report_spec_digest[:32] + "..."],
            ["Source Snapshot Digest", prov_sec.source_snapshot_digest[:32] + "..."],
            ["Selection Policy", prov_sec.selection_policy],
            ["Font Licenses", ", ".join(prov_sec.font_licenses)],
        ]
        for receipt in prov_sec.diagram_receipts:
            tpl = receipt.accepted.reference.binding.slot.template or "diagram"
            prov_data.append([f"Receipt: {tpl}", str(receipt.receipt_id)])

        t_prov = Table(
            [
                [Paragraph(f"<b>{r[0]}</b>", body_style), Paragraph(r[1], body_style)]
                for r in prov_data
            ],
            colWidths=[180, 343],
        )
        t_prov.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t_prov)

        # Build document with deterministic canvas
        doc.build(story, canvasmaker=DeterministicCanvas)
        pdf_bytes = buffer.getvalue()

        # Validate with pypdf
        page_count = self._validate_rendered_pdf(pdf_bytes, spec)

        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        return RenderedReport(
            media_type="application/pdf",
            pdf_bytes=pdf_bytes,
            sha256=pdf_sha256,
            size_bytes=len(pdf_bytes),
            page_count=page_count,
            report_spec_digest=spec.report_spec_digest,
            renderer_profile_digest=prepared.renderer_profile_digest,
            validation_version="1.0.0",
        )

    def _render_diagram_drawing(
        self,
        diag: ReportDiagramInput,
        placement: ReportDiagramPlacement,
        font_body: str,
        font_bold: str,
    ) -> Drawing:
        """Render C2 layout boxes, routes, and labels into a ReportLab Drawing."""
        width_pt = 523.0
        height_pt = 260.0 if "compact" in placement.slot_id else 450.0

        drawing = Drawing(width_pt, height_pt)
        # Background box
        drawing.add(
            Rect(
                0,
                0,
                width_pt,
                height_pt,
                fillColor=colors.HexColor("#FAFAFA"),
                strokeColor=colors.HexColor("#E2E8F0"),
                strokeWidth=0.5,
                rx=3,
                ry=3,
            )
        )

        layout = diag.prepared_diagram.layout
        bounds = layout.bounds
        src_w = (
            max(100.0, float(bounds.width) / 1000.0)
            if hasattr(bounds, "width")
            else 600.0
        )
        src_h = (
            max(100.0, float(bounds.height) / 1000.0)
            if hasattr(bounds, "height")
            else 400.0
        )

        scale_x = (width_pt - 40.0) / src_w
        scale_y = (height_pt - 40.0) / src_h
        scale = min(scale_x, scale_y)

        # Draw Title inside drawing
        drawing.add(
            String(
                12,
                height_pt - 18,
                f"{diag.template.value.replace('_', ' ').title()} View",
                fontName=font_bold,
                fontSize=9,
                fillColor=colors.HexColor("#2D3748"),
            )
        )

        group = Group()
        group.translate(20, 20)

        # Draw Nodes
        nodes = getattr(layout, "nodes", ())
        for node in nodes:
            x_mcss = float(getattr(node, "x", 0)) / 1000.0
            y_mcss = float(getattr(node, "y", 0)) / 1000.0
            w_mcss = float(getattr(node, "width", 80_000)) / 1000.0
            h_mcss = float(getattr(node, "height", 30_000)) / 1000.0

            # Transform into drawing coordinate space
            x = x_mcss * scale
            y = (src_h - (y_mcss + h_mcss)) * scale
            w = w_mcss * scale
            h = h_mcss * scale

            group.add(
                Rect(
                    x,
                    y,
                    w,
                    h,
                    fillColor=colors.HexColor("#FFFFFF"),
                    strokeColor=colors.HexColor("#4A5568"),
                    strokeWidth=1,
                    rx=2,
                    ry=2,
                )
            )

            label = getattr(node, "label", getattr(node, "id", "node"))
            group.add(
                String(
                    x + 4,
                    y + (h / 2) - 3,
                    str(label)[:25],
                    fontName=font_body,
                    fontSize=max(6.0, 7.5 * scale),
                    fillColor=colors.HexColor("#1A202C"),
                )
            )

        # Draw Routes / Edges
        routes = getattr(layout, "routes", ())
        for route in routes:
            points = getattr(route, "points", ())
            for i in range(len(points) - 1):
                p1, p2 = points[i], points[i + 1]
                x1 = (float(p1[0]) / 1000.0) * scale
                y1 = (src_h - (float(p1[1]) / 1000.0)) * scale
                x2 = (float(p2[0]) / 1000.0) * scale
                y2 = (src_h - (float(p2[1]) / 1000.0)) * scale
                group.add(
                    Line(
                        x1,
                        y1,
                        x2,
                        y2,
                        strokeColor=colors.HexColor("#718096"),
                        strokeWidth=0.8,
                    )
                )

        # Empty view indication if zero nodes
        if not nodes:
            group.add(
                String(
                    src_w * scale / 3,
                    src_h * scale / 2,
                    f"Authoritative Empty View: {diag.template.value}",
                    fontName=font_body,
                    fontSize=8,
                    fillColor=colors.HexColor("#A0AEC0"),
                )
            )

        drawing.add(group)
        return drawing

    def _validate_rendered_pdf(self, pdf_bytes: bytes, spec: ReportSpec) -> int:
        """Validate rendered PDF byte structure using pypdf 7.1.1 per §15.5.5."""
        if not pdf_bytes.startswith(b"%PDF-"):
            raise ReportContractError("Rendered bytes lack valid PDF header")
        if b"%%EOF" not in pdf_bytes[-1024:]:
            raise ReportContractError("Rendered bytes lack valid %%EOF marker")

        reader = PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            raise ReportContractError("Rendered report PDF must not be encrypted")

        page_count = len(reader.pages)
        if page_count < 1:
            raise ReportContractError("Rendered PDF contains 0 pages")

        # Security check: inspect root trailer catalog for prohibited actions
        trailer = getattr(reader, "trailer", None) or {}
        catalog = trailer.get("/Root", {}) if isinstance(trailer, dict) else {}
        if isinstance(catalog, dict):
            if "/JavaScript" in catalog:
                raise ReportContractError(
                    "Prohibited /JavaScript action found in PDF catalog"
                )
            if "/OpenAction" in catalog:
                oa = catalog["/OpenAction"]
                if isinstance(oa, dict) and oa.get("/S") in ("/JavaScript", "/Launch"):
                    raise ReportContractError(
                        f"Prohibited /OpenAction {oa.get('/S')} found"
                    )

        return page_count
