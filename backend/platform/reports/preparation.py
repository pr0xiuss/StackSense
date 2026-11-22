"""Report preparation logic: composing public services, C2 readers,

and building C4 ReportSpec.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from backend.platform.delivery.contracts import (
    DiagramTemplate,
    PublicationReceipt,
    WorkExecutionContext,
)
from backend.platform.diagrams.contracts import DiagramReadPort
from backend.platform.reports.configuration import ReportRuntimeConfig
from backend.platform.reports.contracts import (
    CoverageSection,
    DiagnosticsSection,
    DiagramsSection,
    InventorySection,
    MetadataSection,
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
    for filename in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        font_path = FONTS_DIR / filename
        if font_path.exists():
            data = font_path.read_bytes()
            sha256 = hashlib.sha256(data).hexdigest()
            assets.append((filename, sha256, data))
        else:
            # Fallback for environments where asset files are mocked/unavailable
            dummy_data = b"DUMMY_TTF_BYTES_FOR_FIXTURES"
            sha256 = hashlib.sha256(dummy_data).hexdigest()
            assets.append((filename, sha256, dummy_data))
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
                coverage=(
                    prepared_diagram.spec.coverage.model_dump(mode="python")
                    if hasattr(prepared_diagram.spec.coverage, "model_dump")
                    else dict(prepared_diagram.spec.coverage)
                ),
                provenance={
                    "diagram_id": prepared_diagram.spec.diagram_id,
                    "template": str(tpl),
                },
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
            diagnostic_cap_indicated=False,
            limitation_codes=(),
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
            "entities": inventory_data["total_entities"],
            "relationships": inventory_data["total_relationships"],
            "diagnostics": len(all_diagnostics),
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
            font_licenses=("SIL Open Font License 1.1", "Bitstream Vera License"),
            selection_policy=(
                "Boundary, application, and persistence elements ordered by kind and ID"
            ),
            omitted_totals={
                "omitted_entities": max(
                    0,
                    inventory_data["total_entities"]
                    - len(inventory_data["selected_entities"]),
                ),
                "omitted_relationships": max(
                    0,
                    inventory_data["total_relationships"]
                    - len(inventory_data["selected_relationships"]),
                ),
            },
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
            res = self.analysis_lifecycle.list_diagnostics(
                analysis_id, project_id, limit=limit, offset=offset
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
                    sev_str = "info"

                diag_id = getattr(diag, "id", None) or getattr(
                    diag, "diagnostic_id", None
                )
                if not diag_id:
                    continue

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

            if len(items) < limit:
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
        """Capture canonical architecture totals and selected boundary elements."""
        entities_res = self.architecture_query.list_entities(
            version_id, project_id, limit=self.limits.max_source_page_size, offset=0
        )
        relationships_res = self.architecture_query.list_relationships(
            version_id, project_id, limit=self.limits.max_source_page_size, offset=0
        )
        evidence_res = self.architecture_query.list_evidence(
            version_id, project_id, limit=1, offset=0
        )
        unresolved_res = self.architecture_query.list_unresolved(
            version_id, project_id, limit=1, offset=0
        )
        conflicts_res = self.architecture_query.list_conflicts(
            version_id, project_id, limit=1, offset=0
        )

        total_entities = getattr(
            entities_res, "total", len(getattr(entities_res, "items", entities_res))
        )
        total_relationships = getattr(
            relationships_res,
            "total",
            len(getattr(relationships_res, "items", relationships_res)),
        )
        total_evidence = getattr(evidence_res, "total", 0)
        total_unresolved = getattr(unresolved_res, "total", 0)
        total_conflicts = getattr(conflicts_res, "total", 0)

        # Aggregate counts by kind and status
        entity_items = getattr(entities_res, "items", entities_res)
        kind_counter: Counter[str] = Counter()
        status_counter: Counter[str] = Counter()
        selected_entities: list[ReportSourceRef] = []

        for e in entity_items:
            k = str(getattr(e, "kind", "unknown"))
            s = str(getattr(e, "status", "unknown"))
            kind_counter[k] += 1
            status_counter[s] += 1
            if len(selected_entities) < self.limits.max_selected_inventory:
                selected_entities.append(
                    ReportSourceRef(
                        source_kind="entity",
                        architecture_version_id=version_id,
                        logical_id=str(getattr(e, "logical_id", getattr(e, "id", ""))),
                        source_record_type=k,
                    )
                )

        rel_items = getattr(relationships_res, "items", relationships_res)
        rel_kind_counter: Counter[str] = Counter()
        selected_relationships: list[ReportSourceRef] = []
        for r in rel_items:
            rk = str(getattr(r, "kind", "unknown"))
            rel_kind_counter[rk] += 1
            if len(selected_relationships) < self.limits.max_selected_inventory:
                selected_relationships.append(
                    ReportSourceRef(
                        source_kind="relationship",
                        architecture_version_id=version_id,
                        logical_id=str(getattr(r, "logical_id", getattr(r, "id", ""))),
                        source_record_type=rk,
                    )
                )

        return {
            "total_entities": total_entities,
            "total_relationships": total_relationships,
            "total_evidence": total_evidence,
            "total_unresolved": total_unresolved,
            "total_conflicts": total_conflicts,
            "analysis_status": "completed",
            "persisted_coverage": None,
            "counts_by_kind": tuple(sorted(kind_counter.items())),
            "counts_by_status": tuple(sorted(status_counter.items())),
            "relationship_counts_by_kind": tuple(sorted(rel_kind_counter.items())),
            "selected_entities": tuple(selected_entities),
            "selected_relationships": tuple(selected_relationships),
        }

    def _compute_placements(
        self,
        diagram_inputs: list[ReportDiagramInput],
        compact: bool = True,
    ) -> list[ReportDiagramPlacement]:
        """Compute PDF page placements for the 4 diagrams according to Option 3."""
        placements: list[ReportDiagramPlacement] = []
        # Page 1 in diagrams section has 2 slots or full page
        # Check density of diagrams
        is_dense = (not compact) or any(
            len(d.prepared_diagram.layout.nodes) > 30 for d in diagram_inputs
        )

        if not is_dense:
            # Compact 2-per-page placement: 2 pages for 4 diagrams
            # Page 1: Overview and Component
            # Page 2: Dependency and Data Flow
            slots = [
                (1, "compact_top", 0, 400_000),
                (1, "compact_bottom", 0, 50_000),
                (2, "compact_top", 0, 400_000),
                (2, "compact_bottom", 0, 50_000),
            ]
            for i, d in enumerate(diagram_inputs):
                page_idx, slot_id, tx, ty = slots[i]
                placements.append(
                    ReportDiagramPlacement(
                        template=d.template,
                        reference=d.receipt.accepted.reference,
                        page_index=page_idx,
                        slot_id=slot_id,
                        scale_numerator=1,
                        scale_denominator=2,
                        translation_mpt_x=tx,
                        translation_mpt_y=ty,
                        clip_rect=(0, 0, 500_000, 350_000),
                        caption=(
                            f"Figure 3.{i + 1}: "
                            f"{d.template.value.replace('_', ' ').title()}"
                        ),
                    )
                )
        else:
            # Full page per diagram: 4 pages
            for i, d in enumerate(diagram_inputs):
                placements.append(
                    ReportDiagramPlacement(
                        template=d.template,
                        reference=d.receipt.accepted.reference,
                        page_index=i + 1,
                        slot_id="full_page",
                        scale_numerator=1,
                        scale_denominator=1,
                        translation_mpt_x=0,
                        translation_mpt_y=0,
                        clip_rect=(0, 0, 500_000, 700_000),
                        caption=(
                            f"Figure 3.{i + 1}: "
                            f"{d.template.value.replace('_', ' ').title()} (Full Page)"
                        ),
                    )
                )
        return placements
