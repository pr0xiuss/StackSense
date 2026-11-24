"""Report preparation logic: composing public services, C2 readers,

and building C4 ReportSpec.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

from backend.platform.delivery.contracts import (
    DiagramTemplate,
    PublicationReceipt,
    WorkExecutionContext,
)
from backend.platform.diagrams.contracts import DiagramReadPort
from backend.platform.reports.configuration import ReportRuntimeConfig
from backend.platform.reports.contracts import (
    AnalysisCoverage,
    CoverageSection,
    DiagnosticsSection,
    DiagramProvenance,
    DiagramsSection,
    InventorySection,
    MetadataSection,
    OmittedTotals,
    PreparedReport,
    ProvenanceSection,
    ReportContractError,
    ReportCoverage,
    ReportDiagnostic,
    ReportDiagramInput,
    ReportDiagramPlacement,
    ReportInputSnapshot,
    ReportMetadata,
    ReportSection,
    ReportSourceKind,
    ReportSourceRef,
    ReportSpec,
)
from backend.platform.reports.model import (
    c4_canonical_bytes,
    c4_report_resource_id,
    c4_report_spec_digest,
    c4_source_snapshot_digest,
)

FONTS_DIR = Path(__file__).resolve().parent.parent / "diagrams" / "assets" / "fonts"


class ArchitectureQueryPort(Protocol):
    def get_version(self, version_id: UUID, project_id: UUID) -> Any: ...
    def list_entities(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any: ...
    def list_relationships(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any: ...
    def list_evidence(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any: ...
    def list_unresolved(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any: ...
    def list_conflicts(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any: ...


class AnalysisLifecyclePort(Protocol):
    def get_analysis(self, analysis_id: UUID, project_id: UUID) -> Any: ...
    def list_diagnostics(
        self,
        analysis_id: UUID,
        project_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Any: ...


def load_verified_font_assets() -> tuple[tuple[str, str, bytes], ...]:
    """Load font assets from verified diagrams directory."""
    assets: list[tuple[str, str, bytes]] = []
    manifest = json.loads((FONTS_DIR / "font-manifest.json").read_bytes())
    if (
        hashlib.sha256((FONTS_DIR / "LICENSE.dejavu.txt").read_bytes()).hexdigest()
        != manifest["license_sha256"]
    ):
        raise ReportContractError("report_font_integrity")
    for item in manifest["files"]:
        data = (FONTS_DIR / item["name"]).read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        if sha256 != item["sha256"] or len(data) != item["size_bytes"]:
            raise ReportContractError("report_font_integrity")
        assets.append((item["name"], sha256, data))
    return tuple(assets)


class ReportPreparer:
    """Orchestrates public source reads and diagram capture to build ReportSpec."""

    def __init__(
        self,
        architecture_query: ArchitectureQueryPort,
        analysis_lifecycle: AnalysisLifecyclePort,
        diagram_reader: DiagramReadPort,
        config: ReportRuntimeConfig | None = None,
    ) -> None:
        self.architecture_query = architecture_query
        self.analysis_lifecycle = analysis_lifecycle
        self.diagram_reader = diagram_reader
        self.config = config or ReportRuntimeConfig()
        self.limits = self.config.limits
        self.profile = self.config.profile

    def prepare(
        self,
        context: WorkExecutionContext,
    ) -> tuple[ReportSpec, ReportInputSnapshot, PreparedReport]:
        """Prepare immutable snapshot and specification from execution context."""
        context.control.checkpoint()
        work = context.attempt.work
        scope = work.scope
        barrier = context.prerequisites
        if barrier is None:
            raise ReportContractError("Report requires BarrierReceipt prerequisites")
        if barrier.scope != scope:
            raise ReportContractError("Barrier scope mismatch with work scope")

        # 1. Read all four diagrams in fixed order
        ordered_templates = (
            DiagramTemplate.OVERVIEW,
            DiagramTemplate.COMPONENT,
            DiagramTemplate.DEPENDENCY,
            DiagramTemplate.DATA_FLOW,
        )

        receipts_by_template: dict[DiagramTemplate, PublicationReceipt] = {}
        for diag_receipt in barrier.diagrams:
            tpl = diag_receipt.accepted.reference.binding.slot.template
            if isinstance(tpl, DiagramTemplate):
                receipts_by_template[tpl] = diag_receipt

        diagram_inputs: list[ReportDiagramInput] = []
        diagram_assets: list[tuple[str, str, bytes]] = []
        for tpl in ordered_templates:
            receipt = receipts_by_template.get(tpl)
            if receipt is None:
                raise ReportContractError(f"Missing required diagram template: {tpl}")
            ref = receipt.accepted.reference
            prepared_diagram = self.diagram_reader.read_exact(scope, ref)
            diag_input = ReportDiagramInput(
                receipt=receipt,
                scope=scope,
                template=tpl,
                schema_version="1.0.0",
                profile=ref.binding,
                semantic_digest=prepared_diagram.spec.semantic_digest,
                layout_digest=prepared_diagram.layout.layout_digest,
                member_digests=tuple(
                    (m.member, m.sha256)
                    for m in prepared_diagram.descriptor.manifest.members
                ),
                coverage=prepared_diagram.spec.coverage,
                provenance=DiagramProvenance(
                    diagram_id=prepared_diagram.spec.diagram_id, template=tpl
                ),
                prepared_diagram=prepared_diagram,
            )
            diagram_inputs.append(diag_input)
            spec_bytes = prepared_diagram.spec.to_bytes()
            diagram_assets.append(
                (
                    f"{tpl.value}-spec.json",
                    hashlib.sha256(spec_bytes).hexdigest(),
                    spec_bytes,
                )
            )

        context.control.checkpoint()

        # 2. Capture Authoritative Diagnostics
        all_diagnostics = self._capture_diagnostics(scope.analysis_id, scope.project_id)
        context.control.checkpoint()

        # 3. Capture Canonical Architecture
        inventory_data = self._capture_inventory(
            scope.architecture_version_id, scope.project_id
        )
        context.control.checkpoint()

        # 4. Coverage and Limitations
        coverage = ReportCoverage(
            total_entities=inventory_data["total_entities"],
            total_relationships=inventory_data["total_relationships"],
            total_evidence=inventory_data["total_evidence"],
            total_unresolved=inventory_data["total_unresolved"],
            total_conflicts=inventory_data["total_conflicts"],
            analysis_status=inventory_data["analysis_status"],
            persisted_coverage=inventory_data.get("persisted_coverage"),
            selected_inventory_count=len(inventory_data["selected_entities"]),
            omitted_inventory_count=max(
                0,
                inventory_data["total_entities"]
                - len(inventory_data["selected_entities"]),
            ),
            selected_diagnostic_count=len(all_diagnostics),
            omitted_diagnostic_count=0,
            selected_reference_count=len(inventory_data["selected_entities"])
            + len(inventory_data["selected_relationships"]),
            omitted_reference_count=max(
                0,
                (
                    inventory_data["total_entities"]
                    + inventory_data["total_relationships"]
                )
                - (
                    len(inventory_data["selected_entities"])
                    + len(inventory_data["selected_relationships"])
                ),
            ),
            diagnostic_cap_indicated=None,
            limitation_codes=("diagnostic_cap_observation_unavailable",),
        )

        # 5. Build Placements
        placements = self._compute_placements(diagram_inputs)

        # 6. Compute Metadata & Digests
        font_assets = load_verified_font_assets()
        asset_hashes = tuple(a[1] for a in font_assets)
        font_manifest_digest = hashlib.sha256(
            "".join(sorted(asset_hashes)).encode("utf-8")
        ).hexdigest()

        captured_summary = {
            "inventory": inventory_data,
            "diagnostics": [d.model_dump(mode="python") for d in all_diagnostics],
            "diagrams": [d.model_dump(mode="python") for d in diagram_inputs],
        }
        receipt_ids = tuple(d.receipt.receipt_id for d in diagram_inputs)
        source_snapshot_digest = c4_source_snapshot_digest(
            version_id=scope.architecture_version_id,
            analysis_id=scope.analysis_id,
            canonical_digest=scope.canonical_digest,
            captured_data=captured_summary,
            receipt_ids=receipt_ids,
            asset_hashes=asset_hashes,
        )

        report_id = c4_report_resource_id(
            scope=scope,
            binding=work.binding,
            input_fingerprint=work.input_fingerprint,
        )

        metadata = ReportMetadata(
            report_id=report_id,
            scope=scope,
            profile=work.binding,
            captured_at=datetime.now(UTC),
            project_name=None,
            repository_name=None,
            revision_sha=None,
            display_names_available=False,
            source_snapshot_digest=source_snapshot_digest,
            renderer_version=self.profile.renderer_version,
            font_version=self.profile.font_profile,
            asset_manifest_digest=font_manifest_digest,
            deterministic_mode=self.profile.deterministic_mode,
        )

        # Assemble the 6 ordered sections
        sec1 = MetadataSection(metadata=metadata)
        sec2 = InventorySection(
            counts_by_kind=inventory_data["counts_by_kind"],
            counts_by_status=inventory_data["counts_by_status"],
            relationship_counts_by_kind=inventory_data["relationship_counts_by_kind"],
            selected_entities=inventory_data["selected_entities"],
            selected_relationships=inventory_data["selected_relationships"],
            selected_count=len(inventory_data["selected_entities"]),
            omitted_count=max(
                0,
                inventory_data["total_entities"]
                - len(inventory_data["selected_entities"]),
            ),
        )
        sec3 = DiagramsSection(
            diagram_inputs=tuple(diagram_inputs),
            placements=tuple(placements),
        )
        sec4 = DiagnosticsSection(diagnostics=tuple(all_diagnostics))
        sec5 = CoverageSection(coverage=coverage)
        sec6 = ProvenanceSection(
            source_snapshot_digest=source_snapshot_digest,
            diagram_receipts=tuple(d.receipt for d in diagram_inputs),
            font_licenses=(
                "DejaVu 2.37: Bitstream Vera license and public-domain additions",
            ),
            font_license_notice=(FONTS_DIR / "LICENSE.dejavu.txt").read_text(
                encoding="utf-8"
            ),
            selection_policy=(
                "Boundary, application, and persistence elements ordered by kind and ID"
            ),
            omitted_totals=OmittedTotals(
                omitted_entities=max(
                    0,
                    inventory_data["total_entities"]
                    - len(inventory_data["selected_entities"]),
                ),
                omitted_relationships=max(
                    0,
                    inventory_data["total_relationships"]
                    - len(inventory_data["selected_relationships"]),
                ),
            ),
            source_refs=inventory_data["source_refs"],
        )

        sections: tuple[ReportSection, ...] = (sec1, sec2, sec3, sec4, sec5, sec6)

        report_spec = ReportSpec(
            metadata=metadata,
            sections=sections,
            diagram_inputs=tuple(diagram_inputs),
            coverage=coverage,
            report_spec_digest="",
        )
        report_spec_digest = c4_report_spec_digest(report_spec)
        report_spec = report_spec.model_copy(
            update={"report_spec_digest": report_spec_digest}
        )

        snapshot_bytes = c4_canonical_bytes(report_spec)
        snapshot_digest = hashlib.sha256(snapshot_bytes).hexdigest()
        input_snapshot = ReportInputSnapshot(
            report_spec=report_spec,
            font_assets=font_assets,
            diagram_assets=tuple(diagram_assets),
            snapshot_digest=snapshot_digest,
            snapshot_size_bytes=len(snapshot_bytes),
            captured_at=metadata.captured_at,
        )

        prepared_report = PreparedReport(
            spec=report_spec,
            font_assets=font_assets,
            page_placements=tuple(placements),
            renderer_profile_digest=self.profile.profile_digest(),
            limits_digest=self.limits.limits_digest(),
        )

        return report_spec, input_snapshot, prepared_report

    def _capture_diagnostics(
        self, analysis_id: UUID, project_id: UUID
    ) -> list[ReportDiagnostic]:
        """Offset-paged capture of all diagnostics preserving original severity."""
        captured: list[ReportDiagnostic] = []
        offset = 0
        limit = self.limits.max_source_page_size
        severity_order: dict[str, int] = {
            "critical": 0,
            "error": 1,
            "warning": 2,
            "info": 3,
        }

        while True:
            if offset >= self.limits.max_cumulative_source_rows:
                raise ReportContractError("report_limit_exceeded")
            res = self.analysis_lifecycle.list_diagnostics(
                analysis_id, project_id, limit=min(100, limit), offset=offset
            )
            items = getattr(res, "items", res) if hasattr(res, "items") else res
            if not items:
                break
            for diag in items:
                # Severity validation
                raw_sev = getattr(diag, "severity", "info")
                sev_str = str(
                    raw_sev.value if hasattr(raw_sev, "value") else raw_sev
                ).lower()
                if sev_str not in ("info", "warning", "error", "critical"):
                    raise ReportContractError("report_contract_unsupported")

                diag_id = getattr(diag, "id", None) or getattr(
                    diag, "diagnostic_id", None
                )
                if not diag_id:
                    raise ReportContractError("report_contract_unsupported")

                source_ref = ReportSourceRef(
                    source_kind="analysis_diagnostic",
                    analysis_id=analysis_id,
                    artifact_id=getattr(diag, "artifact_id", None),
                    path=getattr(diag, "artifact_path", None)
                    or getattr(diag, "path", None),
                    line=getattr(diag, "source_line", None)
                    or getattr(diag, "line", None),
                    column=getattr(diag, "source_column", None)
                    or getattr(diag, "column", None),
                )

                created_at = getattr(diag, "created_at", None) or datetime.now(UTC)
                if not hasattr(created_at, "tzinfo") or created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)

                rep_diag = ReportDiagnostic(
                    diagnostic_id=diag_id,
                    source_ref=source_ref,
                    severity=sev_str,  # type: ignore[arg-type]
                    code=str(getattr(diag, "code", "diagnostic")),
                    category=str(getattr(diag, "category", "general")),
                    scope=str(getattr(diag, "scope", "analysis")),
                    stage=str(getattr(diag, "stage", "analysis")),
                    message=str(getattr(diag, "message", "")),
                    withheld_reason=getattr(diag, "withheld_reason", None),
                    created_at=created_at,
                    retryability=str(getattr(diag, "retryability", "non_retryable")),
                    artifact_id=source_ref.artifact_id,
                    path=source_ref.path,
                    line=source_ref.line,
                    column=source_ref.column,
                )
                captured.append(rep_diag)

                if len(captured) > self.limits.max_authoritative_diagnostics:
                    msg = (
                        f"Diagnostic count exceeded ceiling of "
                        f"{self.limits.max_authoritative_diagnostics}"
                    )
                    raise ReportContractError(msg)

            if len(items) < min(100, limit):
                break
            offset += len(items)

        # Sort display order: critical, error, warning, info, then stage, code, UUID
        captured.sort(
            key=lambda d: (
                severity_order.get(d.severity, 4),
                d.stage,
                d.code,
                str(d.diagnostic_id),
            )
        )
        return captured

    def _capture_inventory(self, version_id: UUID, project_id: UUID) -> dict[str, Any]:
        """Count every public row, retain only a bounded deterministic selection."""
        version = self.architecture_query.get_version(version_id, project_id)
        analysis = self.analysis_lifecycle.get_analysis(version.analysis_id, project_id)
        totals: dict[str, int] = {}
        kind_counter: Counter[str] = Counter()
        status_counter: Counter[str] = Counter()
        rel_counter: Counter[str] = Counter()
        selections: dict[str, list[ReportSourceRef]] = {
            "entities": [],
            "relationships": [],
        }
        source_refs: list[ReportSourceRef] = []
        calls = rows = 0
        for collection in (
            "entities",
            "relationships",
            "evidence",
            "unresolved",
            "conflicts",
        ):
            offset = 0
            total: int | None = None
            while total is None or offset < total:
                if calls >= self.limits.max_source_calls:
                    raise ReportContractError("report_limit_exceeded")
                page = getattr(self.architecture_query, "list_" + collection)(
                    version_id,
                    project_id,
                    limit=self.limits.max_source_page_size,
                    offset=offset,
                )
                calls += 1
                items = page.items
                if total is None:
                    total = page.total
                if page.total != total or (not items and offset < total):
                    raise ReportContractError("report_selection_drift")
                rows += len(items)
                if rows > self.limits.max_cumulative_source_rows:
                    raise ReportContractError("report_limit_exceeded")
                for item in items:
                    if len(source_refs) < self.limits.max_selected_references:
                        names = (
                            "artifact_id",
                            "source_fact_key",
                            "path",
                            "producer_id",
                            "producer_version",
                            "strength",
                            "polarity",
                            "source_record_type",
                        )
                        source_refs.append(
                            ReportSourceRef(
                                source_kind=cast(
                                    ReportSourceKind,
                                    {
                                        "entities": "entity",
                                        "relationships": "relationship",
                                        "evidence": "evidence",
                                        "unresolved": "unresolved",
                                        "conflicts": "conflict",
                                    }[collection],
                                ),
                                architecture_version_id=version_id,
                                logical_id=getattr(item, "logical_id", None),
                                **{
                                    name: getattr(item, name)
                                    for name in names
                                    if getattr(item, name, None) is not None
                                },
                            )
                        )
                    if collection == "entities":
                        kind_counter[item.kind] += 1
                        status_counter[item.status] += 1
                    elif collection == "relationships":
                        rel_counter[item.kind] += 1
                    if collection in selections:
                        kind = item.kind
                        if collection == "entities" and kind not in {
                            "application",
                            "service",
                            "controller",
                            "component",
                            "endpoint",
                            "database",
                            "data_repository",
                            "external_service",
                            "external_api",
                            "message_broker",
                            "queue",
                            "infrastructure",
                        }:
                            continue
                        selected = selections[collection]
                        selected.append(
                            ReportSourceRef(
                                source_kind=(
                                    "entity"
                                    if collection == "entities"
                                    else "relationship"
                                ),
                                architecture_version_id=version_id,
                                artifact_id=item.id,
                                logical_id=item.logical_id,
                                source_record_type=kind,
                                namespace=getattr(item, "namespace", None),
                                source_logical_id=getattr(
                                    item, "source_logical_id", None
                                ),
                                target_logical_id=getattr(
                                    item, "target_logical_id", None
                                ),
                            )
                        )
                        selected.sort(
                            key=lambda ref: (
                                ref.source_record_type or "",
                                (ref.logical_id or "").encode("utf-8"),
                                str(ref.artifact_id),
                            )
                        )
                        del selected[self.limits.max_selected_inventory :]
                offset += len(items)
                if total == 0:
                    break
            totals[collection] = total or 0
        completeness = getattr(analysis, "completeness", None)
        coverage = (
            None
            if completeness is None
            else AnalysisCoverage(
                **{
                    key: getattr(completeness, key)
                    for key in AnalysisCoverage.model_fields
                }
            )
        )
        return {
            "total_entities": totals["entities"],
            "total_relationships": totals["relationships"],
            "total_evidence": totals["evidence"],
            "total_unresolved": totals["unresolved"],
            "total_conflicts": totals["conflicts"],
            "analysis_status": analysis.status,
            "persisted_coverage": coverage,
            "counts_by_kind": tuple(sorted(kind_counter.items())),
            "counts_by_status": tuple(sorted(status_counter.items())),
            "relationship_counts_by_kind": tuple(sorted(rel_counter.items())),
            "selected_entities": tuple(selections["entities"]),
            "selected_relationships": tuple(selections["relationships"]),
            "source_refs": tuple(source_refs),
        }

    def _compute_placements(
        self, diagram_inputs: list[ReportDiagramInput], compact: bool = True
    ) -> list[ReportDiagramPlacement]:
        """Pack readable unchanged vectors; otherwise tile at a readable scale."""
        from fractions import Fraction
        from math import ceil

        result: list[ReportDiagramPlacement] = []
        page = 1

        def minimum(d: ReportDiagramInput) -> float:
            # Frozen C2 font profile prepares regular14px/bold12px, not the
            # padded label-box height. Preserve the actual six-point floor.
            sizes = [
                12 if glyph.font == "bold" else 14
                for glyph in d.prepared_diagram.layout.glyphs
            ]
            return self.profile.min_readable_font_pt / min(sizes, default=14)

        def fit(d: ReportDiagramInput, w: int, h: int) -> float:
            b = d.prepared_diagram.layout.bounds
            return min(0.75, w / max(b.width, 1), h / max(b.height, 1))

        def emit(
            d: ReportDiagramInput,
            slot: str,
            scale: float,
            x: int,
            y: int,
            w: int,
            h: int,
            row: int | None = None,
            col: int | None = None,
        ) -> None:
            b = d.prepared_diagram.layout.bounds
            rational = Fraction(str(scale)).limit_denominator(1000000)
            result.append(
                ReportDiagramPlacement(
                    template=d.template,
                    reference=d.receipt.accepted.reference,
                    page_index=page,
                    slot_id=slot,
                    scale_numerator=rational.numerator,
                    scale_denominator=rational.denominator,
                    translation_mpt_x=x - int(b.x * scale),
                    translation_mpt_y=y + int(b.y * scale),
                    clip_rect=(x, y, x + w, y + h),
                    tile_row=row,
                    tile_column=col,
                    caption=d.template.value.replace("_", " ").title(),
                )
            )

        i = 0
        while i < len(diagram_inputs):
            # Try a 2x2 grid, then vertical slots, consecutive templates only.
            four = diagram_inputs[i : i + 4]
            if (
                compact
                and len(four) == 4
                and all(fit(d, 245000, 310000) >= minimum(d) for d in four)
            ):
                for j, d in enumerate(four):
                    emit(
                        d,
                        "compact_grid_" + str(j),
                        fit(d, 245000, 310000),
                        36000 + (j % 2) * 270000,
                        420000 - (j // 2) * 350000,
                        245000,
                        310000,
                    )
                i += 4
                page += 1
                continue
            pair = diagram_inputs[i : i + 2]
            if (
                compact
                and len(pair) == 2
                and all(fit(d, 523000, 310000) >= minimum(d) for d in pair)
            ):
                for j, d in enumerate(pair):
                    emit(
                        d,
                        "compact_" + str(j),
                        fit(d, 523000, 310000),
                        36000,
                        420000 - j * 350000,
                        523000,
                        310000,
                    )
                i += 2
                page += 1
                continue
            d = diagram_inputs[i]
            portrait = fit(d, 523000, 650000)
            landscape = fit(d, 769000, 400000)
            if max(portrait, landscape) >= minimum(d):
                wide = landscape > portrait
                emit(
                    d,
                    "full_landscape" if wide else "full_page",
                    landscape if wide else portrait,
                    36000,
                    90000,
                    769000 if wide else 523000,
                    400000 if wide else 650000,
                )
                page += 1
            else:
                scale = minimum(d)
                b = d.prepared_diagram.layout.bounds
                width, height = b.width * scale, b.height * scale
                columns = max(1, ceil(max(0, width - 523000) / 503000) + 1)
                rows = max(1, ceil(max(0, height - 650000) / 630000) + 1)
                if (
                    columns > self.profile.max_tile_columns
                    or rows > self.profile.max_tile_rows
                ):
                    raise ReportContractError("report_limit_exceeded")
                if rows * columns + len(result) > self.limits.max_diagram_tiles:
                    raise ReportContractError("report_limit_exceeded")
                for row in range(rows):
                    for col in range(columns):
                        emit(d, "tile", scale, 36000, 90000, 523000, 650000, row, col)
                        p = result[-1]
                        result[-1] = p.model_copy(
                            update={
                                "translation_mpt_x": p.translation_mpt_x - col * 503000,
                                "translation_mpt_y": p.translation_mpt_y + row * 630000,
                            }
                        )
                        page += 1
            i += 1
        return result
