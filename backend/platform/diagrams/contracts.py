"""Closed C2 v1 schemas. Values do not prove physical sealing or acceptance."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, Literal, Protocol, Self, get_args
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StrictInt,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from backend.platform.analysis.architecture.model import (
    ArchitectureEntityKind as Kind,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureEvidencePolarity as Polarity,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureEvidenceStrength as Strength,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureFactStatus as Status,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureRelationshipKind as Rel,
)
from backend.platform.delivery.contracts import (
    ArtifactReference,
    DiagramTemplate,
    HandlerProfile,
    VersionScope,
    WorkKind,
)
from backend.platform.diagrams.model import (
    canonical_bytes,
    digest,
    load_json,
    normalize_sets,
)

C2_VERSION = "1.0.0"
N = Annotated[StrictInt, Field(ge=0, le=2**53 - 1)]
Positive = Annotated[StrictInt, Field(gt=0, le=2**53 - 1)]
H = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Id = Annotated[str, Field(pattern=r"^(diagram://|d[ngepl]:|gl:)[0-9a-f]{64}$")]
Coordinate = Annotated[StrictInt, Field(ge=-(10**9), le=10**9)]
Dimension = Annotated[StrictInt, Field(ge=0, le=10**9)]
Direction = Literal["outgoing", "incoming", "both"]
OmissionReason = Literal[
    "granularity",
    "filter",
    "depth",
    "scene_budget",
    "bundle",
    "collapsed",
    "unavailable_source",
    "unsupported_detail",
    "label_clipped",
]
ErrorCode = Literal[
    "diagram_authentication_required",
    "diagram_forbidden",
    "diagram_not_found",
    "diagram_not_ready",
    "diagram_scope_mismatch",
    "diagram_generation_changed",
    "diagram_cursor_invalid",
    "diagram_cursor_expired",
    "diagram_generation_unavailable",
    "diagram_input_invalid",
    "diagram_contract_unsupported",
    "diagram_limit_exceeded",
    "diagram_range_unsupported",
    "diagram_runtime_unavailable",
    "diagram_store_unavailable",
    "diagram_source_unavailable",
    "diagram_timeout",
    "diagram_integrity_error",
    "diagram_internal_error",
]


def _text(value: str, limit: int) -> str:
    if len(value.encode("utf-8", "strict")) > limit:
        raise ValueError("C2 text exceeds byte limit")
    return value


Text = Annotated[str, AfterValidator(lambda v: _text(v, 4096))]
LogicalId = Annotated[str, AfterValidator(lambda v: _text(v, 8192))]
Short = Annotated[str, AfterValidator(lambda v: _text(v, 256))]
T128 = Annotated[str, AfterValidator(lambda v: _text(v, 128))]
T1024 = Annotated[str, AfterValidator(lambda v: _text(v, 1024))]


class ClosedRecord(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    @model_serializer(mode="wrap")
    def canonical_sets(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        # Pydantic has already serialized every nested ClosedRecord using this
        # same hook. Sort this record's sets once, not the entire subtree again.
        # Raw digest payloads still use recursive normalization in model.digest.
        return dict(normalize_sets(handler(self), shallow=True))

    @field_validator("*", mode="after")
    @classmethod
    def unicode_scalar(cls, value: object) -> object:
        if isinstance(value, str):
            value.encode("utf-8", "strict")
        return value

    @field_validator("protocol", "protocol_version", mode="before", check_fields=False)
    @classmethod
    def integer_protocol(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("protocol version requires an integer")
        return value

    @field_validator(
        "id",
        "project_id",
        "repository_id",
        "analysis_id",
        "snapshot_id",
        "architecture_version_id",
        "artifact_id",
        "generation_id",
        "base_generation_id",
        "request_id",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def canonical_uuids(cls, value: object, info: ValidationInfo) -> object:
        if info.field_name is not None:
            annotation = cls.model_fields[info.field_name].annotation
            if (annotation is UUID or UUID in get_args(annotation)) and isinstance(
                value, str
            ):
                if str(UUID(value)) != value:
                    raise ValueError("noncanonical C2 UUID")
                if info.mode == "json":
                    return UUID(value)
        return value

    @classmethod
    def from_bytes(cls, data: bytes, *, max_bytes: int) -> Self:
        # Validate raw duplicate keys/numbers before Pydantic's JSON conversion.
        load_json(data, max_bytes=max_bytes)
        return cls.model_validate_json(data)

    def to_bytes(self) -> bytes:
        # Revalidation catches unsafe model_construct/model_copy(update=...).
        type(self).model_validate(self)
        return canonical_bytes(self)


class CanonicalDiagramScope(ClosedRecord):
    project_id: UUID
    repository_id: UUID
    analysis_id: UUID
    snapshot_id: UUID
    architecture_version_id: UUID
    sequence_number: Positive
    canonical_digest: H
    architecture_schema_version: Literal["1.0.0"]
    ir_schema_version: Literal["1.0.0"]

    @classmethod
    def from_delivery(cls, scope: VersionScope) -> Self:
        return cls.model_validate({k: getattr(scope, k) for k in cls.model_fields})


class ErrorDetails(ClosedRecord):
    dimension: Annotated[str, AfterValidator(lambda v: _text(v, 64))] | None
    actual: N | None
    limit: N | None
    request_id: UUID | None


class DiagramErrorBody(ClosedRecord):
    code: ErrorCode
    message: Short
    details: ErrorDetails


class ErrorResponse(ClosedRecord):
    error: DiagramErrorBody


class Ref(ClosedRecord):
    record_type: Literal["entity", "relationship", "evidence", "unresolved", "conflict"]
    id: UUID
    logical_id: LogicalId


class EntityRef(Ref):
    record_type: Literal["entity"]


class RelationshipRef(Ref):
    record_type: Literal["relationship"]


class EvidenceRef(Ref):
    record_type: Literal["evidence"]


class SemanticProfile(ClosedRecord):
    template_version: Literal["1.0.0"]
    builder_version: Literal["1.0.0"]
    selection_version: Literal["1.0.0"]
    identity_version: Literal["1.0.0"]
    fingerprint: H


class ViewBase(ClosedRecord):
    root_ids: tuple[EntityRef, ...]
    entity_kinds: tuple[Kind, ...]
    statuses: tuple[Status, ...]
    relationship_kinds: tuple[Rel, ...]
    include_contains: bool
    depth: Annotated[N, Field(le=8)]
    selected_entity_ids: tuple[EntityRef, ...]


class OverviewView(ViewBase):
    template: Literal[DiagramTemplate.OVERVIEW]
    layers: tuple[
        Literal["applications", "interfaces", "processing", "persistence", "external"],
        ...,
    ]
    boundary_ids: tuple[EntityRef, ...]


class MultipleParents(ClosedRecord):
    child: EntityRef
    parents: tuple[EntityRef, ...]
    layout_parent: EntityRef | None


class ComponentView(ViewBase):
    template: Literal[DiagramTemplate.COMPONENT]
    multi_parent: tuple[MultipleParents, ...]
    containment_cycles: tuple[tuple[EntityRef, ...], ...]


class DependencyView(ViewBase):
    template: Literal[DiagramTemplate.DEPENDENCY]
    direction: Direction
    sccs: tuple[tuple[EntityRef, ...], ...]
    scc_scope: Literal["selected_view"]


class DataFlowView(ViewBase):
    template: Literal[DiagramTemplate.DATA_FLOW]
    semantics: Literal["static_interactions"]
    connectivity_overlay: bool
    no_flow_reason: Literal["no_established_data_flow", "insufficient_evidence"] | None


ViewDefinition = Annotated[
    OverviewView | ComponentView | DependencyView | DataFlowView,
    Field(discriminator="template"),
]


class DiagramNode(ClosedRecord):
    id: Id
    entity: EntityRef
    kind: Kind
    name: Text
    namespace: Annotated[tuple[T1024, ...], Field(max_length=64)]
    status: Status
    evidence: tuple[EvidenceRef, ...]
    group_id: Id | None
    category: Literal[
        "application",
        "interface",
        "processing",
        "persistence",
        "external",
        "implementation",
        "unknown",
    ]


class RelationshipMember(ClosedRecord):
    relationship: RelationshipRef
    kind: Rel
    source: EntityRef
    target: EntityRef
    status: Status
    evidence: tuple[EvidenceRef, ...]


class DiagramEdge(ClosedRecord):
    id: Id
    source_visual_id: Id
    target_visual_id: Id
    members: Annotated[tuple[RelationshipMember, ...], Field(min_length=1)]
    label: Short
    bundle: bool

    @model_validator(mode="after")
    def homogeneous_bundle(self) -> Self:
        if self.bundle != (len(self.members) > 1):
            raise ValueError("edge bundle cardinality mismatch")
        if len({(m.kind, m.status) for m in self.members}) != 1:
            raise ValueError("competing relationship kinds/statuses cannot bundle")
        _unique(tuple(str(m.relationship.id) for m in self.members))
        return self


class DiagramGroup(ClosedRecord):
    id: Id
    kind: Literal[
        "canonical_container", "namespace_bucket", "selected_scc", "presentation_layer"
    ]
    label: Text
    container: EntityRef | None
    parent_group_id: Id | None
    visible_member_ids: tuple[Id, ...]
    membership_count: N
    collapsed_default: bool
    rule: T128


class GroupMembership(ClosedRecord):
    group_id: Id
    members: tuple[EntityRef, ...]


class OmittedRecord(ClosedRecord):
    record: Ref
    reason: OmissionReason


class MembershipCatalog(ClosedRecord):
    membership_schema_version: Literal["1.0.0"]
    diagram_id: Id
    groups: tuple[GroupMembership, ...]
    omitted: tuple[OmittedRecord, ...]


class EvidenceProvenance(ClosedRecord):
    record: EvidenceRef
    source_record_type: T128
    producer_id: Short | None
    producer_version: T128 | None
    artifact_id: UUID | None
    source_fact_key: LogicalId | None
    path: Text
    source_range: Mapping[str, N] | None
    strength: Strength
    polarity: Polarity

    @field_validator("source_range")
    @classmethod
    def freeze_range(cls, value: Mapping[str, int] | None) -> Mapping[str, int] | None:
        if value is None:
            return None
        if len(value) > 16:
            raise ValueError("source range capacity exceeded")
        for key in value:
            _text(key, 64)
        return MappingProxyType(dict(value))

    @field_serializer("source_range")
    def range_json(self, value: Mapping[str, int] | None) -> dict[str, int] | None:
        return None if value is None else dict(value)


class Annotation(ClosedRecord):
    kind: Literal[
        "unresolved",
        "conflict",
        "omission",
        "containment_cycle",
        "multiple_parents",
        "label_limitation",
    ]
    subject_ids: tuple[Id, ...]
    records: tuple[Ref, ...]
    evidence: tuple[EvidenceRef, ...]
    reason: Short
    count: N | None


class LegendItem(ClosedRecord):
    key: T128
    label: Annotated[str, AfterValidator(lambda v: _text(v, 512))]
    meaning: T1024


class CompletenessSnapshot(ClosedRecord):
    total_inventory_artifacts: N
    analyzed_artifacts: N
    failed_artifacts: N
    total_syntax_documents: N
    total_syntax_facts: N
    source_entities: N
    source_relationships: N
    source_unresolved_references: N
    source_conflicts: N
    architecture_entities: N
    architecture_relationships: N
    architecture_unresolved_relationships: N
    architecture_conflicts: N
    is_partial: bool


class Count(ClosedRecord):
    collection: Literal[
        "entities", "relationships", "evidence", "unresolved", "conflicts", "groups"
    ]
    kind: T128 | None
    scanned: N
    eligible: N | None
    represented: N
    excluded: N | None
    omitted: N | None

    @model_validator(mode="after")
    def arithmetic(self) -> Self:
        if self.represented > self.scanned:
            raise ValueError("represented count exceeds scanned count")
        if (
            self.excluded is not None
            and self.represented + self.excluded > self.scanned
        ):
            raise ValueError("invalid C2 excluded counts")
        if self.eligible is not None:
            if self.represented > self.eligible or self.eligible > self.scanned:
                raise ValueError("invalid C2 coverage counts")
            if (
                self.omitted is not None
                and self.represented + self.omitted > self.eligible
            ):
                raise ValueError("invalid C2 omission counts")
        return self


class Coverage(ClosedRecord):
    view_state: Literal["complete_view", "bounded_view", "partial_view", "empty_view"]
    source_partial: bool
    selection_bounded: bool
    scan_exhausted: bool
    source_completeness: CompletenessSnapshot
    counts: tuple[Count, ...]
    reasons: tuple[OmissionReason, ...]


class DiagramSpec(ClosedRecord):
    diagram_schema_version: Literal["1.0.0"]
    scope: CanonicalDiagramScope
    template: DiagramTemplate
    profile: SemanticProfile
    diagram_id: Id
    view: ViewDefinition
    nodes: Annotated[tuple[DiagramNode, ...], Field(max_length=1000)]
    edges: Annotated[tuple[DiagramEdge, ...], Field(max_length=4000)]
    groups: Annotated[tuple[DiagramGroup, ...], Field(max_length=256)]
    annotations: Annotated[tuple[Annotation, ...], Field(max_length=10000)]
    provenance: Annotated[tuple[EvidenceProvenance, ...], Field(max_length=75000)]
    membership_digest: H
    coverage: Coverage
    legend: Annotated[tuple[LegendItem, ...], Field(max_length=64)]
    semantic_digest: H

    @model_validator(mode="after")
    def template_and_digest(self) -> Self:
        if self.view.template != self.template:
            raise ValueError("diagram/view template mismatch")
        if not self.diagram_id.startswith("diagram://"):
            raise ValueError("invalid diagram ID domain")
        expected = digest(
            "ss.diagram.semantic",
            self.model_dump(mode="json", exclude={"semantic_digest"}),
        )
        if expected != self.semantic_digest:
            raise ValueError("diagram semantic digest mismatch")
        return self


class LayoutProfile(ClosedRecord):
    id: Literal[
        "architecture_compound_v1",
        "dependency_layered_v1",
        "static_flow_v1",
        "simple_layered_v1",
    ]
    version: Literal["1.0.0"]
    engine: Literal["elkjs"]
    engine_version: Literal["0.12.1"]
    runtime_version: Literal["24.22.3"]
    font_profile: Literal["dejavu_paths_2_37_v1"]
    fingerprint: H


class Point(ClosedRecord):
    x: Coordinate
    y: Coordinate


class Box(Point):
    width: Dimension
    height: Dimension


class PositionedBox(ClosedRecord):
    id: Id
    box: Box


class Port(ClosedRecord):
    id: Id
    owner_id: Id
    point: Point


class PathCommand(ClosedRecord):
    command: Literal["M", "L", "Q", "C", "Z"]
    operands: tuple[Coordinate, ...]

    @model_validator(mode="after")
    def arity(self) -> Self:
        if len(self.operands) != {"M": 2, "L": 2, "Q": 4, "C": 6, "Z": 0}[self.command]:
            raise ValueError("invalid glyph command arity")
        return self


class Glyph(ClosedRecord):
    id: Id
    font: Literal["regular", "bold"]
    commands: tuple[PathCommand, ...]


class GlyphPlacement(ClosedRecord):
    glyph_id: Id
    origin: Point


class LabelGeometry(ClosedRecord):
    id: Id
    owner_id: Id
    box: Box
    display_text: Text
    original_text: Text
    glyphs: tuple[GlyphPlacement, ...]
    escaped: bool
    clipped: bool


class RouteSection(ClosedRecord):
    start: Point
    bends: tuple[Point, ...]
    end: Point


class EdgeRoute(ClosedRecord):
    edge_id: Id
    sections: Annotated[tuple[RouteSection, ...], Field(min_length=1)]


class LayoutSpec(ClosedRecord):
    layout_schema_version: Literal["1.0.0"]
    diagram_id: Id
    semantic_digest: H
    profile: LayoutProfile
    unit: Literal["milli_css_px"]
    nodes: Annotated[tuple[PositionedBox, ...], Field(max_length=1000)]
    groups: Annotated[tuple[PositionedBox, ...], Field(max_length=256)]
    ports: tuple[Port, ...]
    labels: tuple[LabelGeometry, ...]
    routes: Annotated[tuple[EdgeRoute, ...], Field(max_length=4000)]
    glyphs: Annotated[tuple[Glyph, ...], Field(max_length=1024)]
    font_notice: Annotated[str, AfterValidator(lambda v: _text(v, 16384))]
    bounds: Box
    fallback: Literal["none", "simple_layered"]
    limitations: tuple[Short, ...]
    layout_digest: H

    @model_validator(mode="after")
    def valid_digest(self) -> Self:
        expected = digest(
            "ss.diagram.layout", self.model_dump(mode="json", exclude={"layout_digest"})
        )
        if expected != self.layout_digest:
            raise ValueError("diagram layout digest mismatch")
        return self


class MemberDescriptor(ClosedRecord):
    member: Literal["spec", "layout", "members", "svg"]
    file_name: Literal["spec.json", "layout.json", "members.json", "scene.svg"]
    media_type: Literal["application/json", "image/svg+xml"]
    schema_version: Literal["1.0.0"]
    size_bytes: N
    sha256: H

    @model_validator(mode="after")
    def exact_member(self) -> Self:
        name = "scene.svg" if self.member == "svg" else f"{self.member}.json"
        media = "image/svg+xml" if self.member == "svg" else "application/json"
        if (self.file_name, self.media_type) != (name, media):
            raise ValueError("artifact member mapping mismatch")
        return self


class DiagramArtifactManifest(ClosedRecord):
    artifact_schema_version: Literal["1.0.0"]
    scope: VersionScope
    binding: HandlerProfile
    input_fingerprint: H
    diagram_id: Id
    generation_id: UUID
    artifact_id: UUID
    semantic_digest: H
    layout_digest: H
    membership_digest: H
    export_profile: Literal["svg_paths_v1"]
    members: Annotated[tuple[MemberDescriptor, ...], Field(min_length=4, max_length=4)]
    verification_version: Literal["1.0.0"]

    @model_validator(mode="after")
    def member_set(self) -> Self:
        if tuple(m.member for m in self.members) != (
            "layout",
            "members",
            "spec",
            "svg",
        ):
            raise ValueError("artifact requires exact sorted member set")
        if self.binding.slot.kind != WorkKind.DIAGRAM:
            raise ValueError("artifact requires diagram profile")
        if not self.diagram_id.startswith("diagram://"):
            raise ValueError("invalid artifact diagram ID domain")
        return self


class DiagramArtifactDescriptor(ClosedRecord):
    manifest: DiagramArtifactManifest
    reference: ArtifactReference

    @model_validator(mode="after")
    def exact_reference(self) -> Self:
        m, r = self.manifest, self.reference
        if any(
            getattr(m, k) != getattr(r, k)
            for k in (
                "scope",
                "binding",
                "input_fingerprint",
                "generation_id",
                "artifact_id",
            )
        ):
            raise ValueError("artifact descriptor/reference mismatch")
        content = m.to_bytes()
        if (
            r.size_bytes != len(content)
            or r.digests.content != hashlib.sha256(content).hexdigest()
            or r.digests.spec != m.semantic_digest
            or r.digests.layout != m.layout_digest
        ):
            raise ValueError("artifact reference digest/size mismatch")
        return self


class PreparedDiagram(ClosedRecord):
    spec: DiagramSpec
    layout: LayoutSpec
    descriptor: DiagramArtifactDescriptor

    @model_validator(mode="after")
    def matching_parts(self) -> Self:
        s, layout, m = self.spec, self.layout, self.descriptor.manifest
        if (
            s.scope != CanonicalDiagramScope.from_delivery(m.scope)
            or not s.template == m.binding.slot.template
            or not s.diagram_id == layout.diagram_id == m.diagram_id
            or not s.semantic_digest == layout.semantic_digest == m.semantic_digest
            or layout.layout_digest != m.layout_digest
            or s.membership_digest != m.membership_digest
        ):
            raise ValueError("prepared diagram binding mismatch")
        for name, value in (("spec", s), ("layout", layout)):
            member = next(x for x in m.members if x.member == name)
            # Nested fields were just revalidated by Pydantic (always). Hash
            # their canonical bytes without validating that whole graph again.
            # Public to_bytes still revalidates unsafe model_copy/construct input.
            data = canonical_bytes(value)
            if (
                member.size_bytes != len(data)
                or member.sha256 != hashlib.sha256(data).hexdigest()
            ):
                raise ValueError("prepared member byte mismatch")
        return self


class DiagramViewRequest(ClosedRecord):
    root_ids: Annotated[tuple[UUID, ...], Field(max_length=32)]
    entity_kinds: tuple[Kind, ...]
    statuses: tuple[Status, ...]
    relationship_kinds: tuple[Rel, ...]
    include_contains: bool
    depth: Annotated[N, Field(le=8)]
    direction: Direction
    collapsed_group_ids: Annotated[tuple[Id, ...], Field(max_length=64)]
    selected_entity_ids: Annotated[tuple[UUID, ...], Field(max_length=200)]


class DiagramViewResponse(ClosedRecord):
    base_generation_id: UUID
    base_semantic_digest: H
    request_digest: H
    spec: DiagramSpec
    layout: LayoutSpec

    @model_validator(mode="after")
    def matching_layout(self) -> Self:
        if (self.spec.diagram_id, self.spec.semantic_digest) != (
            self.layout.diagram_id,
            self.layout.semantic_digest,
        ):
            raise ValueError("view spec/layout binding mismatch")
        return self


class DiagramReadPort(Protocol):
    def read_exact(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> PreparedDiagram: ...


class VerifiedMemberHandle(Protocol):
    """Reader-owned bounded handle; close must release its durable read pin."""

    def read(self, size: int) -> bytes: ...

    def close(self) -> None: ...


class DiagramMemberReadPort(Protocol):
    def open_exact(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        member: Literal["spec", "layout", "members", "svg"],
    ) -> VerifiedMemberHandle: ...


class DiagramViewPort(Protocol):
    def view(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        request: DiagramViewRequest,
    ) -> DiagramViewResponse: ...


def _unique[T](values: tuple[T, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError("duplicate C2 identity")
