"""Closed C4 v1 schemas for Architecture Analysis Report.

These immutable values define the report specification, preparation,
diagram embedding placements, coverage, provenance, and artifact manifests.
Constructing a value is never proof of physical sealing or publication.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Protocol, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from backend.platform.delivery.artifacts import VerifiedArtifactHandle
from backend.platform.delivery.contracts import (
    ArtifactReference,
    DiagramTemplate,
    HandlerProfile,
    PublicationReceipt,
    VersionScope,
)
from backend.platform.diagrams.contracts import PreparedDiagram

C4_VERSION: Literal["1.0.0"] = "1.0.0"
REPORT_TYPE: Literal["architecture_analysis"] = "architecture_analysis"
TEMPLATE_NAME: Literal["architecture_analysis_v1"] = "architecture_analysis_v1"

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonnegativeInt = Annotated[StrictInt, Field(ge=0)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]

ReportSourceKind = Literal[
    "analysis_diagnostic",
    "entity",
    "relationship",
    "evidence",
    "unresolved",
    "conflict",
]

ReportDiagnosticSeverity = Literal[
    "info",
    "warning",
    "error",
    "critical",
]

ReportSectionKind = Literal[
    "metadata",
    "inventory",
    "diagrams",
    "diagnostics",
    "coverage",
    "provenance",
]


class ReportContractError(ValueError):
    """Raised on invalid report contract invariants."""


class FrozenReportModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )

    @field_validator("*", mode="after")
    @classmethod
    def valid_unicode(cls, value: object) -> object:
        if isinstance(value, str):
            value.encode("utf-8", errors="strict")
        return value

    @classmethod
    def from_bytes(cls, data: bytes, *, max_bytes: int | None = None) -> Self:
        if max_bytes is not None and len(data) > max_bytes:
            raise ValueError("size_bytes_exceeded")
        return cls.model_validate_json(data)

    def to_bytes(self) -> bytes:
        from backend.platform.reports.model import c4_canonical_bytes

        return c4_canonical_bytes(self)


class ReportSourceRef(FrozenReportModel):
    """Reference to an authoritative source record or evidence item."""

    source_kind: ReportSourceKind
    analysis_id: UUID | None = None
    architecture_version_id: UUID | None = None
    source_record_type: str | None = None
    artifact_id: UUID | None = None
    source_fact_key: str | None = None
    path: str | None = None
    line: int | None = None
    column: int | None = None
    logical_id: str | None = None
    producer_id: str | None = None
    producer_version: str | None = None
    strength: str | None = None
    polarity: str | None = None


class ReportDiagnostic(FrozenReportModel):
    """Authoritative analysis diagnostic preserved verbatim with original severity."""

    diagnostic_id: UUID
    source_ref: ReportSourceRef
    severity: ReportDiagnosticSeverity
    code: str
    category: str
    scope: str
    stage: str
    message: str
    withheld_reason: str | None = None
    created_at: AwareDatetime
    retryability: str
    artifact_id: UUID | None = None
    path: str | None = None
    line: int | None = None
    column: int | None = None
    evidence_refs: tuple[ReportSourceRef, ...] = ()

    @field_validator("created_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class ReportCoverage(FrozenReportModel):
    """Canonical and analysis completeness metrics and explicit selection counts."""

    total_entities: NonnegativeInt
    total_relationships: NonnegativeInt
    total_evidence: NonnegativeInt
    total_unresolved: NonnegativeInt
    total_conflicts: NonnegativeInt

    analysis_status: str
    persisted_coverage: dict[str, Any] | None = None

    selected_inventory_count: NonnegativeInt
    omitted_inventory_count: NonnegativeInt
    selected_diagnostic_count: NonnegativeInt
    omitted_diagnostic_count: NonnegativeInt
    selected_reference_count: NonnegativeInt
    omitted_reference_count: NonnegativeInt

    diagnostic_cap_indicated: bool = False
    limitation_codes: tuple[str, ...] = ()


class ReportMetadata(FrozenReportModel):
    """Top-level immutable report provenance and scope identity."""

    c4_version: Literal["1.0.0"] = C4_VERSION
    schema_version: str = "1.0.0"
    template: str = TEMPLATE_NAME
    report_type: Literal["architecture_analysis"] = REPORT_TYPE
    report_id: UUID
    scope: VersionScope
    profile: HandlerProfile
    captured_at: AwareDatetime

    project_name: str | None = None
    repository_name: str | None = None
    revision_sha: str | None = None
    display_names_available: bool = False

    source_snapshot_digest: Digest
    renderer_version: str
    font_version: str
    asset_manifest_digest: Digest
    deterministic_mode: str = "pinned_canonical_v1"

    @field_validator("captured_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class ReportDiagramInput(FrozenReportModel):
    """Complete prepared diagram input matching publication receipt."""

    receipt: PublicationReceipt
    scope: VersionScope
    template: DiagramTemplate
    schema_version: str = "1.0.0"
    profile: HandlerProfile
    semantic_digest: Digest
    layout_digest: Digest
    member_digests: tuple[tuple[str, str], ...]
    coverage: dict[str, Any]
    provenance: dict[str, Any]
    prepared_diagram: PreparedDiagram

    @model_validator(mode="after")
    def validate_diagram_match(self) -> ReportDiagramInput:
        if self.template != self.receipt.accepted.reference.binding.slot.template:
            raise ReportContractError("Diagram template mismatch with receipt")
        if self.scope != self.receipt.accepted.reference.scope:
            raise ReportContractError("Diagram scope mismatch with receipt")
        if self.semantic_digest != self.prepared_diagram.spec.semantic_digest:
            raise ReportContractError("Semantic digest mismatch")
        if self.layout_digest != self.prepared_diagram.layout.layout_digest:
            raise ReportContractError("Layout digest mismatch")
        return self


class ReportDiagramPlacement(FrozenReportModel):
    """PDF-presentation-only placement record for an embedded diagram."""

    template: DiagramTemplate
    reference: ArtifactReference
    page_index: PositiveInt
    slot_id: str
    scale_numerator: PositiveInt
    scale_denominator: PositiveInt
    translation_mpt_x: int
    translation_mpt_y: int
    clip_rect: tuple[int, int, int, int]
    tile_row: NonnegativeInt | None = None
    tile_column: NonnegativeInt | None = None
    caption: str = ""

    @model_validator(mode="after")
    def validate_clip_rect(self) -> ReportDiagramPlacement:
        min_x, min_y, max_x, max_y = self.clip_rect
        if min_x > max_x or min_y > max_y:
            raise ReportContractError("Invalid clip rectangle coordinates")
        return self


class MetadataSection(FrozenReportModel):
    section_kind: Literal["metadata"] = "metadata"
    title: str = "Executive Metadata & Cover"
    metadata: ReportMetadata


class InventorySection(FrozenReportModel):
    section_kind: Literal["inventory"] = "inventory"
    title: str = "Architecture Inventory & Boundaries"
    counts_by_kind: tuple[tuple[str, int], ...]
    counts_by_status: tuple[tuple[str, int], ...]
    relationship_counts_by_kind: tuple[tuple[str, int], ...]
    selected_entities: tuple[ReportSourceRef, ...]
    selected_relationships: tuple[ReportSourceRef, ...]
    selected_count: NonnegativeInt
    omitted_count: NonnegativeInt


class DiagramsSection(FrozenReportModel):
    section_kind: Literal["diagrams"] = "diagrams"
    title: str = "Architecture Diagrams"
    diagram_inputs: tuple[ReportDiagramInput, ...]
    placements: tuple[ReportDiagramPlacement, ...]


class DiagnosticsSection(FrozenReportModel):
    section_kind: Literal["diagnostics"] = "diagnostics"
    title: str = "Authoritative Analysis Diagnostics"
    diagnostics: tuple[ReportDiagnostic, ...]
    empty_disclaimer: str = (
        "No analysis diagnostics were reported for this architecture version. "
        "This indicates zero detected issues in analysis, "
        "not verified runtime correctness."
    )


class CoverageSection(FrozenReportModel):
    section_kind: Literal["coverage"] = "coverage"
    title: str = "Coverage, Uncertainty & Limitations"
    coverage: ReportCoverage


class ProvenanceSection(FrozenReportModel):
    section_kind: Literal["provenance"] = "provenance"
    title: str = "Provenance, Licenses & Appendix"
    source_snapshot_digest: Digest
    diagram_receipts: tuple[PublicationReceipt, ...]
    font_licenses: tuple[str, ...]
    selection_policy: str
    omitted_totals: dict[str, int]


ReportSection = Annotated[
    MetadataSection
    | InventorySection
    | DiagramsSection
    | DiagnosticsSection
    | CoverageSection
    | ProvenanceSection,
    Field(discriminator="section_kind"),
]


class ReportSpec(FrozenReportModel):
    """Closed deterministic architecture analysis report specification."""

    c4_version: Literal["1.0.0"] = C4_VERSION
    report_type: Literal["architecture_analysis"] = REPORT_TYPE
    metadata: ReportMetadata
    sections: tuple[ReportSection, ...]
    diagram_inputs: tuple[ReportDiagramInput, ...]
    coverage: ReportCoverage
    report_spec_digest: str = ""

    @model_validator(mode="after")
    def validate_spec_structure(self) -> ReportSpec:
        expected_sections = (
            "metadata",
            "inventory",
            "diagrams",
            "diagnostics",
            "coverage",
            "provenance",
        )
        actual_sections = tuple(s.section_kind for s in self.sections)
        if actual_sections != expected_sections:
            raise ReportContractError(
                f"Sections must be exactly {expected_sections}, got {actual_sections}"
            )

        if len(self.diagram_inputs) != 4:
            raise ReportContractError("ReportSpec requires exactly four diagram inputs")

        ordered_templates = (
            DiagramTemplate.OVERVIEW,
            DiagramTemplate.COMPONENT,
            DiagramTemplate.DEPENDENCY,
            DiagramTemplate.DATA_FLOW,
        )
        actual_templates = tuple(d.template for d in self.diagram_inputs)
        if actual_templates != ordered_templates:
            msg = (
                f"Diagram inputs must be in fixed order {ordered_templates}, "
                f"got {actual_templates}"
            )
            raise ReportContractError(msg)
        return self


class ReportInputSnapshot(FrozenReportModel):
    """Internal serializable snapshot of all inputs required to render the report."""

    report_spec: ReportSpec
    font_assets: tuple[tuple[str, str, bytes], ...]  # (filename, sha256, bytes)
    diagram_assets: tuple[tuple[str, str, bytes], ...]  # (diagram_id, sha256, bytes)
    snapshot_digest: Digest
    snapshot_size_bytes: NonnegativeInt
    captured_at: AwareDatetime

    @field_validator("captured_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class PreparedReport(FrozenReportModel):
    """Immutable bundle passed to the isolated renderer."""

    spec: ReportSpec
    font_assets: tuple[tuple[str, str, bytes], ...]
    page_placements: tuple[ReportDiagramPlacement, ...]
    renderer_profile_digest: Digest
    limits_digest: Digest


class RenderedReport(FrozenReportModel):
    """Result of PDF rendering before sealing and verification."""

    media_type: Literal["application/pdf"] = "application/pdf"
    pdf_bytes: bytes = Field(exclude=True)
    sha256: Digest
    size_bytes: NonnegativeInt
    page_count: PositiveInt
    report_spec_digest: Digest
    renderer_profile_digest: Digest
    validation_version: Literal["1.0.0"] = "1.0.0"


class ReportArtifactMember(FrozenReportModel):
    """Member descriptor for sealed report artifact bundle."""

    member: Literal["spec", "pdf"]
    file_name: str
    media_type: str
    schema_version: str = "1.0.0"
    size_bytes: NonnegativeInt
    sha256: Digest


class ReportArtifactManifest(FrozenReportModel):
    """Top-level sealed report manifest describing the immutable artifact."""

    artifact_schema_version: Literal["1.0.0"] = "1.0.0"
    scope: VersionScope
    binding: HandlerProfile
    input_fingerprint: Digest

    attempt_id: UUID
    work_id: UUID
    run_id: UUID
    candidate_id: UUID
    fence_token: PositiveInt
    epoch: UUID

    resource_id: UUID
    generation_id: UUID
    artifact_id: UUID

    source_snapshot_digest: Digest
    report_spec_digest: Digest
    render_fingerprint: Digest

    diagram_receipt_ids: tuple[UUID, ...]
    diagram_member_digests: tuple[str, ...]
    page_placement_digest: Digest
    page_count: PositiveInt

    members: tuple[ReportArtifactMember, ...]
    verification_version: Literal["1.0.0"] = "1.0.0"

    def to_bytes(self) -> bytes:
        from backend.platform.reports.model import c4_canonical_bytes

        return c4_canonical_bytes(self)


class ReportArtifactDescriptor(FrozenReportModel):
    reference: ArtifactReference
    manifest: ReportArtifactManifest


# API DTO contracts for M6 consumer fixtures
class ReportSlotStatus(FrozenReportModel):
    status: str
    waiting_on: tuple[str, ...] = ()
    reference: ArtifactReference | None = None


class ReportSummary(FrozenReportModel):
    scope: VersionScope
    report_id: UUID
    report_type: Literal["architecture_analysis"] = REPORT_TYPE
    profile: HandlerProfile
    input_fingerprint: Digest
    availability: str
    readability: str
    reference: ArtifactReference | None = None
    pdf_size_bytes: NonnegativeInt | None = None
    pdf_sha256: Digest | None = None
    page_count: PositiveInt | None = None
    spec_digest: Digest | None = None
    created_at: AwareDatetime
    accepted_at: AwareDatetime | None = None
    observed_at: AwareDatetime

    @field_validator("created_at", "accepted_at", "observed_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(UTC)


class ReportCollection(FrozenReportModel):
    scope: VersionScope
    automatic: ReportSlotStatus
    items: tuple[ReportSummary, ...]
    next_cursor: str | None = None


class ReportGenerationSummary(FrozenReportModel):
    generation_id: UUID
    artifact_id: UUID
    accepted_at: AwareDatetime
    page_count: PositiveInt
    pdf_size_bytes: NonnegativeInt
    pdf_sha256: Digest
    report_spec_digest: Digest
    reference: ArtifactReference

    @field_validator("accepted_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class ReportGenerationPage(FrozenReportModel):
    scope: VersionScope
    report_id: UUID
    items: tuple[ReportGenerationSummary, ...]
    next_cursor: str | None = None


class ReportReadPort(Protocol):
    """Port for reading published report specifications and PDF handles."""

    def read_exact(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> tuple[ReportSpec, ReportArtifactManifest]: ...

    def open_exact(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        member: Literal["spec", "pdf"] = "pdf",
    ) -> VerifiedArtifactHandle: ...
