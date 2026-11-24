"""Validation logic for C4 ReportSpec, sections, placements, and constraints."""

from __future__ import annotations

from collections.abc import Sequence

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import (
    C4_VERSION,
    DiagramsSection,
    ReportContractError,
    ReportDiagramPlacement,
    ReportSpec,
)
from backend.platform.reports.model import c4_canonical_bytes, c4_report_spec_digest


class ReportValidator:
    """Validates ReportSpec invariants, digest integrity, and limit boundaries."""

    def __init__(self, limits: ReportLimits | None = None) -> None:
        self.limits = limits or ReportLimits()

    def validate(self, spec: ReportSpec) -> None:
        """Thorough validation of report specification."""
        if spec.c4_version != C4_VERSION:
            raise ReportContractError(f"Unsupported C4 version: {spec.c4_version}")
        if spec.report_type != "architecture_analysis":
            raise ReportContractError(f"Unsupported report type: {spec.report_type}")

        # 1. Section order validation
        expected_sections = (
            "metadata",
            "inventory",
            "diagrams",
            "diagnostics",
            "coverage",
            "provenance",
        )
        actual_sections = tuple(s.section_kind for s in spec.sections)
        if actual_sections != expected_sections:
            raise ReportContractError(
                f"Sections must be exactly {expected_sections}, got {actual_sections}"
            )

        # 2. Diagrams validation
        ordered_templates = (
            DiagramTemplate.OVERVIEW,
            DiagramTemplate.COMPONENT,
            DiagramTemplate.DEPENDENCY,
            DiagramTemplate.DATA_FLOW,
        )
        if len(spec.diagram_inputs) != 4:
            raise ReportContractError(
                f"ReportSpec requires exactly 4 diagram inputs, "
                f"found {len(spec.diagram_inputs)}"
            )
        actual_templates = tuple(d.template for d in spec.diagram_inputs)
        if actual_templates != ordered_templates:
            raise ReportContractError(
                f"Diagram inputs must follow template order {ordered_templates}, "
                f"got {actual_templates}"
            )

        scope = spec.metadata.scope
        for diag in spec.diagram_inputs:
            if diag.scope != scope:
                raise ReportContractError(
                    f"Diagram {diag.template} scope mismatch with report scope"
                )

        # 3. Placement validation
        diagrams_section = next(
            s for s in spec.sections if isinstance(s, DiagramsSection)
        )
        self._validate_placements(diagrams_section.placements, ordered_templates)
        references = {
            d.template: d.receipt.accepted.reference for d in spec.diagram_inputs
        }
        if any(
            p.reference != references[p.template] for p in diagrams_section.placements
        ):
            raise ReportContractError("report placement reference mismatch")
        if len(diagrams_section.placements) > self.limits.max_diagram_tiles:
            raise ReportContractError("report_limit_exceeded")
        if (
            len(c4_canonical_bytes(spec.model_dump(mode="python")))
            > self.limits.max_spec_bytes
        ):
            raise ReportContractError("report_limit_exceeded")

        # 4. Diagnostic limits validation
        diag_section = next(s for s in spec.sections if s.section_kind == "diagnostics")
        diagnostics = getattr(diag_section, "diagnostics", ())
        if len(diagnostics) > self.limits.max_authoritative_diagnostics:
            msg = (
                f"Diagnostic count {len(diagnostics)} exceeds limit "
                f"{self.limits.max_authoritative_diagnostics}"
            )
            raise ReportContractError(msg)

        # 5. Digest validation
        if spec.report_spec_digest:
            expected_digest = c4_report_spec_digest(spec)
            if spec.report_spec_digest != expected_digest:
                msg = (
                    f"Report spec digest mismatch: expected {expected_digest}, "
                    f"got {spec.report_spec_digest}"
                )
                raise ReportContractError(msg)

        try:
            ReportSpec.model_validate(spec)
        except ValueError as exc:
            raise ReportContractError(str(exc)) from exc

    def _validate_placements(
        self,
        placements: Sequence[ReportDiagramPlacement],
        required_templates: Sequence[DiagramTemplate],
    ) -> None:
        """Validate diagram placements on PDF pages."""
        if not placements:
            raise ReportContractError(
                "Diagram section must contain at least one placement"
            )

        placed_templates = {p.template for p in placements}
        for req in required_templates:
            if req not in placed_templates:
                raise ReportContractError(
                    f"Required diagram template {req} has no page placement"
                )

        # Ensure no overlapping slot/clip on the same page
        slots_by_page: dict[int, set[str]] = {}
        boxes_by_page: dict[int, list[tuple[int, int, int, int]]] = {}
        for p in placements:
            if p.scale_numerator <= 0 or p.scale_denominator <= 0:
                raise ReportContractError("Placement scales must be positive integers")
            min_x, min_y, max_x, max_y = p.clip_rect
            if min_x >= max_x or min_y >= max_y:
                raise ReportContractError(f"Invalid placement clip rect: {p.clip_rect}")

            page_slots = slots_by_page.setdefault(p.page_index, set())
            if p.slot_id in page_slots:
                raise ReportContractError(
                    f"Duplicate slot '{p.slot_id}' on diagram page {p.page_index}"
                )
            page_slots.add(p.slot_id)
            width, height = (
                (841890, 595276) if p.slot_id == "full_landscape" else (595276, 841890)
            )
            if (
                min_x < 36000
                or min_y < 36000
                or max_x > width - 36000
                or max_y > height - 36000
            ):
                raise ReportContractError("report placement outside page")
            for x0, y0, x1, y1 in boxes_by_page.setdefault(p.page_index, []):
                if max(min_x, x0) < min(max_x, x1) and max(min_y, y0) < min(max_y, y1):
                    raise ReportContractError("report placements overlap")
            boxes_by_page[p.page_index].append(p.clip_rect)
