"""M4 internal read DTOs; no duplicate delivery lifecycle or authentication."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, field_serializer, model_validator

from backend.platform.delivery.api_contracts import WorkSummary
from backend.platform.delivery.contracts import (
    ArtifactReference,
    DiagramTemplate,
    VersionScope,
)
from backend.platform.diagrams.contracts import (
    CanonicalDiagramScope,
    ClosedRecord,
    Coverage,
    ErrorCode,
    H,
    Id,
    N,
    OmissionReason,
    Ref,
)


class ApiRecord(ClosedRecord):
    @field_serializer("accepted_at", "verified_at", "observed_at", check_fields=False)
    def utc(self, value: datetime | None) -> str | None:
        return (
            value.astimezone(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
            if value
            else None
        )


class DiagramCounts(ApiRecord):
    nodes: N
    edges: N
    groups: N


class DiagramCapabilities(ApiRecord):
    model_config = ConfigDict(validate_by_name=True, serialize_by_alias=True)
    read: bool
    view: bool
    json_export: bool = Field(alias="json")
    svg: bool
    completed_rebuild: Literal[False] = False


class DiagramSummary(ApiRecord):
    template: DiagramTemplate
    canonical_scope: CanonicalDiagramScope
    delivery_scope: VersionScope | None
    work: WorkSummary | None
    availability: Literal[
        "NOT_SCHEDULED",
        "WAITING",
        "BUILDING",
        "READY",
        "FAILED",
        "CANCELLED",
        "UNAVAILABLE",
    ]
    readability: Literal["unknown", "verified", "unavailable"]
    verified_at: datetime | None
    reference: ArtifactReference | None
    coverage: Coverage | None
    counts: DiagramCounts | None
    capabilities: DiagramCapabilities
    reason: ErrorCode | None
    observed_at: datetime


class DiagramCollection(ApiRecord):
    canonical_scope: CanonicalDiagramScope
    items: Annotated[tuple[DiagramSummary, ...], Field(min_length=4, max_length=4)]

    @model_validator(mode="after")
    def template_order(self) -> Self:
        if tuple(item.template for item in self.items) != tuple(DiagramTemplate):
            raise ValueError("diagram collection template order mismatch")
        return self


class GenerationSummary(ApiRecord):
    generation_id: UUID
    reference: ArtifactReference
    accepted_at: datetime
    coverage: Coverage


class GenerationPage(ApiRecord):
    scope: CanonicalDiagramScope
    template: DiagramTemplate
    items: Annotated[tuple[GenerationSummary, ...], Field(max_length=200)]
    next_cursor: Annotated[str, Field(max_length=4096)] | None


class MemberItem(ApiRecord):
    record: Ref
    reason: OmissionReason | None


class MemberPage(ApiRecord):
    generation_id: UUID
    semantic_digest: H
    group_id: Id | None
    items: Annotated[tuple[MemberItem, ...], Field(max_length=200)]
    total: N
    next_cursor: Annotated[str, Field(max_length=4096)] | None
