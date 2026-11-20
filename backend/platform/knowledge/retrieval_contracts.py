"""P5-C3 retrieval request, response, view, and error contracts.

This module defines the transport-neutral C3 candidate contracts for Phase 5
Module 3 (Controlled Retrieval and Evidence Context), adhering to §7A of
PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Final, Literal, Protocol, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from backend.platform.delivery.contracts import VersionScope
from backend.platform.knowledge.model import immutable_value


class C3Model(BaseModel):
    """Defensively freeze JSON containers, including copies revalidated at ports."""

    model_config = ConfigDict(allow_inf_nan=False)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:
        checked = type(self).model_validate(self)
        return BaseModel.model_dump_json(checked, *args, **kwargs)

    @field_validator("*", mode="after")
    @classmethod
    def freeze_containers(cls, value: Any) -> Any:
        import json

        if isinstance(value, (dict, list, tuple)):

            def immutable_json(item: Any) -> Any:
                if isinstance(item, BaseModel) and item.model_config.get("frozen"):
                    return item.model_dump(mode="json")
                if isinstance(item, (UUID, date, datetime)):
                    return str(item)
                raise ValueError("C3 containers require immutable JSON values")

            json.dumps(value, allow_nan=False, default=immutable_json)
            return immutable_value(value)
        return value


C3_CONTRACT_VERSION: Final[Literal["1.0.0"]] = "1.0.0"

DEFAULT_RETRIEVAL_LIMIT: Final[int] = 25
MAX_RETRIEVAL_LIMIT: Final[int] = 100
MAX_QUERY_STRING_LENGTH: Final[int] = 500
MAX_LOGICAL_ID_LENGTH: Final[int] = 1024
MAX_CURSOR_LENGTH: Final[int] = 4096


# --- Controlled Vocabularies & Enums (§7A.4, §7A.8) ---


class RetrievalOperation(StrEnum):
    """Closed vocabulary of authorized C3 retrieval operations."""

    LOOKUP = "lookup"
    RELATIONSHIPS = "relationships"
    DEPENDENCIES = "dependencies"
    DEPENDENTS = "dependents"
    CONTAINMENT = "containment"
    PATHS = "paths"
    EVIDENCE = "evidence"


class ResolutionState(StrEnum):
    """Closed resolution states for subject selectors."""

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    INCOMPLETE = "incomplete"


class RetrievalOutcome(StrEnum):
    """Closed outcome states for query and context responses."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    NO_EVIDENCE = "no_evidence"


class SourceKind(StrEnum):
    """Closed vocabulary of participating retrieval source kinds."""

    CANONICAL = "canonical"
    SEARCH = "search"
    GRAPH = "graph"


class FreshnessState(StrEnum):
    """Closed freshness states for source observations."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class TraversalDirection(StrEnum):
    """Direction for relationship and dependency exploration."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"


class ContainmentDirection(StrEnum):
    """Direction for containment hierarchy exploration."""

    PARENTS = "parents"
    CHILDREN = "children"
    BOTH = "both"


class SelectionRationaleCode(StrEnum):
    """Closed codes explaining why an item was selected into context (§7A.8)."""

    EXPLICIT_IDENTITY = "explicit_identity"
    EXACT_NAME = "exact_name"
    LEXICAL_CANDIDATE = "lexical_candidate"
    DIRECT_RELATIONSHIP = "direct_relationship"
    GRAPH_CONTEXT = "graph_context"
    SUPPORTING_EVIDENCE = "supporting_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


# --- Error Taxonomy (§7A.10) ---


class RetrievalError(Exception):
    """Base exception for all safe M3 retrieval and context errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.safe_details = dict(safe_details) if safe_details else {}
        self.cause = cause


class RetrievalInvalidRequestError(RetrievalError):
    """Input request parameters or selector shapes are malformed or unsupported.

    Maps to HTTP 422.
    """

    def __init__(
        self,
        message: str = "Retrieval request is invalid",
        *,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code="retrieval_invalid_request",
            safe_details=safe_details,
            cause=cause,
        )


class RetrievalCursorInvalidError(RetrievalError):
    """Pagination cursor is forged, malformed, or has mismatched scope/actor."""

    def __init__(
        self,
        message: str = "Retrieval cursor is invalid",
        *,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code="retrieval_cursor_invalid",
            safe_details=safe_details,
            cause=cause,
        )


class RetrievalCursorExpiredError(RetrievalError):
    """Pagination cursor or point-in-time handle expired (HTTP 410)."""

    def __init__(
        self,
        message: str = "Retrieval cursor has expired",
        *,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code="retrieval_cursor_expired",
            safe_details=safe_details,
            cause=cause,
        )


class RetrievalGenerationChangedError(RetrievalError):
    """Active projection generation drifted during read or continuation (HTTP 409)."""

    def __init__(
        self,
        message: str = "Participating generation has changed; please restart query",
        *,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code="retrieval_generation_changed",
            safe_details=safe_details,
            cause=cause,
        )


class RetrievalNotFoundError(RetrievalError):
    """Explicitly requested record identity not found within authorized version.

    Maps to HTTP 404.
    """

    def __init__(
        self,
        message: str = "Requested retrieval subject was not found",
        *,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code="retrieval_not_found",
            safe_details=safe_details,
            cause=cause,
        )


class RetrievalCapacityExceededError(RetrievalError):
    """Operation exceeds configured entity, row, or memory capacity limits."""

    def __init__(
        self,
        message: str = "Retrieval capacity budget exceeded",
        *,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code="retrieval_capacity_exceeded",
            safe_details=safe_details,
            cause=cause,
        )


class RetrievalDeadlineExceededError(RetrievalError):
    """Retrieval operation exceeded total deadline (HTTP 504)."""

    def __init__(
        self,
        message: str = "Retrieval operation timed out",
        *,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code="retrieval_deadline_exceeded",
            safe_details=safe_details,
            cause=cause,
        )


class RetrievalUnavailableError(RetrievalError):
    """Required backend service or policy configuration is unavailable (HTTP 503)."""

    def __init__(
        self,
        message: str = "Retrieval backend service is unavailable",
        *,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code="retrieval_unavailable",
            safe_details=safe_details,
            cause=cause,
        )


class RetrievalIntegrityFailedError(RetrievalError):
    """Data integrity check failed or corrupted records detected (HTTP 500)."""

    def __init__(
        self,
        message: str = "Retrieval integrity check failed",
        *,
        safe_details: dict[str, Any] | None = None,
        cause: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code="retrieval_integrity_failed",
            safe_details=safe_details,
            cause=cause,
        )


# --- DTOs and Immutable Views (§7A.3, §7A.4, §7A.8) ---


class RetrievalPrincipal(C3Model):
    """Authorized calling context verified by trusted delegation (§7A.3)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    actor_id: UUID
    project_id: UUID
    role: str
    correlation_id: str | None = None


class RetrievalScope(C3Model):
    """Exact published architecture version scope derived from header (§7A.5)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    project_id: UUID
    repository_id: UUID
    analysis_id: UUID
    snapshot_id: UUID
    architecture_version_id: UUID
    sequence_number: int = Field(ge=1)
    canonical_digest: str = Field(min_length=64, max_length=64)
    architecture_schema_version: str
    ir_schema_version: str
    published_at: AwareDatetime
    completeness: dict[str, Any] | None = None


RecordKind = Literal["entity", "relationship", "evidence", "unresolved", "conflict"]
SelectorType = Literal["record_id", "logical_id", "entity_name"]


class SubjectSelector(C3Model):
    """Tagged union for subject resolution (§7A.4).

    Exactly one shape must be populated:
    - record_id: {selector_type: "record_id", record_kind: kind, record_id: UUID}
    - logical_id: {selector_type: "logical_id", record_kind: kind, logical_id: str}
    - entity_name: {selector_type: "entity_name", record_kind: "entity",
                    name: str, namespace?: tuple[str, ...]}
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    selector_type: SelectorType
    record_kind: RecordKind = "entity"
    record_id: UUID | None = None
    logical_id: str | None = Field(default=None, max_length=MAX_LOGICAL_ID_LENGTH)
    name: str | None = Field(default=None, max_length=MAX_LOGICAL_ID_LENGTH)
    namespace: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def validate_selector_shape(self) -> Self:
        if self.selector_type == "record_id":
            if self.record_id is None:
                raise ValueError("record_id is required when selector_type='record_id'")
            if (
                self.logical_id is not None
                or self.name is not None
                or self.namespace is not None
            ):
                raise ValueError(
                    "Only record_id may be set when selector_type='record_id'"
                )
        elif self.selector_type == "logical_id":
            if not self.logical_id:
                raise ValueError(
                    "logical_id is required and non-empty "
                    "when selector_type='logical_id'"
                )
            if (
                self.record_id is not None
                or self.name is not None
                or self.namespace is not None
            ):
                raise ValueError(
                    "Only logical_id may be set when selector_type='logical_id'"
                )
        elif self.selector_type == "entity_name":
            if self.record_kind != "entity":
                raise ValueError(
                    "entity_name selector is only valid for record_kind='entity'"
                )
            if not self.name:
                raise ValueError(
                    "name is required and non-empty when selector_type='entity_name'"
                )
            if self.record_id is not None or self.logical_id is not None:
                raise ValueError(
                    "record_id and logical_id must not be set "
                    "when selector_type='entity_name'"
                )
        else:
            raise ValueError(f"Unsupported selector_type: {self.selector_type}")
        return self

    @classmethod
    def from_record_id(
        cls, record_kind: RecordKind, record_id: UUID
    ) -> SubjectSelector:
        return cls(
            selector_type="record_id", record_kind=record_kind, record_id=record_id
        )

    @classmethod
    def from_logical_id(
        cls, record_kind: RecordKind, logical_id: str
    ) -> SubjectSelector:
        return cls(
            selector_type="logical_id", record_kind=record_kind, logical_id=logical_id
        )

    @classmethod
    def from_entity_name(
        cls, name: str, namespace: tuple[str, ...] | None = None
    ) -> SubjectSelector:
        return cls(
            selector_type="entity_name",
            record_kind="entity",
            name=name,
            namespace=namespace,
        )


class SubjectCandidate(C3Model):
    """Candidate match when selector is ambiguous or multiple matches exist (§7A.5)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    record_id: UUID
    logical_id: str
    kind: str
    name: str | None = None
    namespace: tuple[str, ...] | None = None
    reason: str


class ResolvedSubject(C3Model):
    """Deterministic subject resolution outcome (§7A.5, §7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    selector: SubjectSelector
    state: ResolutionState
    selected_id: UUID | None = None
    selected_logical_id: str | None = None
    selected_kind: str | None = None
    candidates: tuple[SubjectCandidate, ...] = ()
    omitted_count: int = Field(default=0, ge=0)
    scan_complete: bool = True


class SourceObservation(C3Model):
    """Observation of participating retrieval source (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    source_kind: SourceKind
    contract_version: str
    scope: RetrievalScope | None = None
    search_scope: VersionScope | None = None
    generation_id: UUID | None = None
    index_uuid: str | None = None
    graph_schema_version: str | None = None
    projector_version: str | None = None
    capabilities: tuple[str, ...] = ()
    freshness: FreshnessState | None = None
    is_current_version: bool | None = None
    freshness_reason: str | None = None
    observed_at: AwareDatetime | None = None
    advisory_only: bool = False
    limitations: tuple[str, ...] = ()


class CanonicalFactView(C3Model):
    """Safe immutable canonical fact view for an entity (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    record_id: UUID
    logical_id: str
    kind: str
    name: str
    namespace: tuple[str, ...] | None = None
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_count: int = Field(default=0, ge=0)
    evidence_references: tuple[str, ...] = ()


class RelationshipView(C3Model):
    """Safe immutable canonical relationship view (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    record_id: UUID
    logical_id: str
    kind: str
    status: str
    source_logical_id: str
    target_logical_id: str
    source_id: UUID | None = None
    target_id: UUID | None = None
    evidence_references: tuple[str, ...] = ()


class EvidenceItemView(C3Model):
    """Safe canonical evidence item metadata without raw source excerpts (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    record_id: UUID
    logical_id: str
    source_record_type: str
    path: str
    artifact_id: UUID | None = None
    range_data: dict[str, Any] | None = None
    polarity: str
    strength: str
    producer_id: str | None = None
    producer_version: str | None = None
    source_fact_key: str | None = None
    subject_references: tuple[str, ...] = ()


class UnresolvedView(C3Model):
    """Safe canonical unresolved relationship view (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    record_id: UUID
    logical_id: str
    reason: str
    unresolved_type: str
    source_logical_id: str | None = None
    target_descriptor: str | None = None
    status: str | None = None
    evidence_references: tuple[str, ...] = ()
    candidate_references: tuple[str, ...] = ()
    details: dict[str, Any] = Field(default_factory=dict)


class ConflictView(C3Model):
    """Safe canonical conflict view (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    record_id: UUID
    logical_id: str
    conflict_type: str
    subject_key: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    evidence_references: tuple[str, ...] = ()


class Coverage(C3Model):
    """Coverage and completeness metadata for retrieval operations (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    considered_count: int = Field(default=0, ge=0)
    selected_count: int = Field(default=0, ge=0)
    scanned_count: int = Field(default=0, ge=0)
    count_known: bool = True
    exhausted: bool = True
    truncated: bool = False
    omission_reasons: tuple[str, ...] = ()


class SelectionRationale(C3Model):
    """Closed rationale explaining why an item was selected in retrieval context.

    Adheres to §7A.8 without natural-language speculation.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    code: SelectionRationaleCode
    target_logical_id: str
    target_kind: str
    originating_operation: RetrievalOperation | None = None
    hit_key: str | None = None
    hop_distance: int | None = None


class OmissionSummary(C3Model):
    """Explicit disclosure of omitted items and constraints (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    source: SourceKind
    reason: str
    omitted_count: int = Field(default=0, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)


class LimitsAndUsage(C3Model):
    """Declared budget limits and actual selection accounting (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    max_facts: int = Field(ge=1)
    max_relationships: int = Field(ge=1)
    max_evidence: int = Field(ge=1)
    max_output_bytes: int = Field(ge=1024)
    facts_count: int = Field(default=0, ge=0)
    relationships_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    unresolved_count: int = Field(default=0, ge=0)
    conflicts_count: int = Field(default=0, ge=0)
    total_output_bytes: int = Field(default=0, ge=0)


class RetrievalPlan(C3Model):
    """Normalized, versioned strategy and budget plan for context assembly (§7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    strategy_version: Literal["1.0.0"] = "1.0.0"
    request_fingerprint: str = Field(min_length=64, max_length=64)
    operations: tuple[RetrievalOperation, ...]
    subjects: tuple[SubjectSelector, ...] = ()
    target: SubjectSelector | None = None
    required_sources: tuple[SourceKind, ...] = (SourceKind.CANONICAL,)
    optional_sources: tuple[SourceKind, ...] = ()
    policy_fingerprint: str = Field(min_length=64, max_length=64)
    budget_snapshot: dict[str, int | float] = Field(default_factory=dict)


class ContextRequest(C3Model):
    """Request schema for immutable multi-subject ContextBundle assembly.

    Adheres to §7A.8 and §7A.10.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    project_id: UUID
    architecture_version_id: UUID
    subjects: tuple[SubjectSelector, ...] = Field(default=(), max_length=100)
    q: str | None = Field(default=None, max_length=MAX_QUERY_STRING_LENGTH)
    operations: tuple[RetrievalOperation, ...] = (
        RetrievalOperation.LOOKUP,
        RetrievalOperation.RELATIONSHIPS,
        RetrievalOperation.EVIDENCE,
    )
    required_sources: tuple[SourceKind, ...] = (SourceKind.CANONICAL,)
    optional_sources: tuple[SourceKind, ...] = (
        SourceKind.SEARCH,
        SourceKind.GRAPH,
    )
    target: SubjectSelector | None = None
    include_evidence: bool = True
    include_conflicts: bool = True
    include_unresolved: bool = True
    budget_overrides: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_context_plan(self) -> Self:
        if not self.subjects and not self.q:
            raise ValueError("Context requires subjects or a literal query")
        if not self.operations or len(set(self.operations)) != len(self.operations):
            raise ValueError("Operations must be nonempty and unique")
        if set(self.required_sources) & set(self.optional_sources):
            raise ValueError("Required and optional sources must be disjoint")
        if RetrievalOperation.PATHS in self.operations and self.target is None:
            raise ValueError("Paths require a target selector")
        if self.budget_overrides:
            raise ValueError("Budget overrides are not enabled")
        return self


class KnowledgeQueryRequest(C3Model):
    """Closed controlled-query request schema (§7A.4)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    project_id: UUID
    architecture_version_id: UUID
    expected_repository_id: UUID | None = None
    expected_analysis_id: UUID | None = None
    expected_snapshot_id: UUID | None = None
    operation: RetrievalOperation
    subject: SubjectSelector | None = None
    target: SubjectSelector | None = None
    q: str | None = Field(default=None, max_length=MAX_QUERY_STRING_LENGTH)
    relationship_kinds: tuple[str, ...] = ()
    document_kinds: tuple[str, ...] = ()
    evidence_entity_ids: tuple[UUID, ...] = ()
    evidence_relationship_ids: tuple[UUID, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    direction: TraversalDirection = TraversalDirection.BOTH
    containment_direction: ContainmentDirection = ContainmentDirection.BOTH
    graph_depth: int | None = Field(default=None, ge=1, le=5)
    limit: int = Field(default=DEFAULT_RETRIEVAL_LIMIT, ge=1, le=MAX_RETRIEVAL_LIMIT)
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)

    @model_validator(mode="after")
    def validate_request_semantics(self) -> Self:
        if self.operation == RetrievalOperation.PATHS:
            if self.subject is None or self.target is None:
                raise ValueError(
                    "Both subject and target selectors are required "
                    "for 'paths' operation"
                )
        if self.operation in (
            RetrievalOperation.RELATIONSHIPS,
            RetrievalOperation.DEPENDENCIES,
            RetrievalOperation.DEPENDENTS,
            RetrievalOperation.CONTAINMENT,
        ):
            if self.subject is None:
                raise ValueError(
                    f"Subject selector is required for '{self.operation.value}' "
                    "operation"
                )
        return self


class CanonicalPathView(C3Model):
    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )
    node_logical_ids: tuple[str, ...]
    relationship_logical_ids: tuple[str, ...]
    hop_count: int = Field(ge=0, le=5)

    @model_validator(mode="after")
    def valid_path(self) -> Self:
        if (
            len(self.node_logical_ids) != self.hop_count + 1
            or len(self.relationship_logical_ids) != self.hop_count
        ):
            raise ValueError("Invalid path structure")
        return self


class KnowledgeQueryResponse(C3Model):
    """Controlled query response schema (§7A.3, §7A.8)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    c3_version: Literal["1.0.0"] = "1.0.0"
    scope: RetrievalScope
    operation: RetrievalOperation
    outcome: RetrievalOutcome = RetrievalOutcome.COMPLETE
    resolved_subject: ResolvedSubject | None = None
    resolved_target: ResolvedSubject | None = None
    facts: tuple[CanonicalFactView, ...] = ()
    relationships: tuple[RelationshipView, ...] = ()
    evidence: tuple[EvidenceItemView, ...] = ()
    unresolved: tuple[UnresolvedView, ...] = ()
    conflicts: tuple[ConflictView, ...] = ()
    source_observations: tuple[SourceObservation, ...] = ()
    coverage: Coverage
    next_cursor: str | None = None
    paths: tuple[CanonicalPathView, ...] = ()


class EvidencePage(C3Model):
    """Bounded paginated evidence items response (§7A.8, §7A.10)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    c3_version: Literal["1.0.0"] = "1.0.0"
    scope: RetrievalScope
    items: tuple[EvidenceItemView, ...] = ()
    total_items: int | None = Field(default=None, ge=0)
    has_more: bool = False
    next_cursor: str | None = None
    coverage: Coverage


class ContextBundle(C3Model):
    """Immutable, validated bounded context bundle with deterministic semantic digest.

    Adheres strictly to §7A.8 specifications.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    c3_version: Literal["1.0.0"] = "1.0.0"
    scope: RetrievalScope
    plan: RetrievalPlan
    policy_fingerprint: str = Field(min_length=64, max_length=64)
    source_observations: tuple[SourceObservation, ...] = ()
    resolved_subjects: tuple[ResolvedSubject, ...] = ()
    facts: tuple[CanonicalFactView, ...] = ()
    relationships: tuple[RelationshipView, ...] = ()
    evidence: tuple[EvidenceItemView, ...] = ()
    unresolved: tuple[UnresolvedView, ...] = ()
    conflicts: tuple[ConflictView, ...] = ()
    rationales: tuple[SelectionRationale, ...] = ()
    coverage: Coverage
    omissions: tuple[OmissionSummary, ...] = ()
    limits_and_usage: LimitsAndUsage
    outcome: RetrievalOutcome
    semantic_digest: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_bundle_integrity(self) -> Self:
        from backend.platform.knowledge.context import compute_c3_semantic_digest

        if self.policy_fingerprint != self.plan.policy_fingerprint:
            raise ValueError("Bundle policy binding mismatch")
        for observation in self.source_observations:
            if observation.scope is not None and observation.scope != self.scope:
                raise ValueError("Bundle source scope mismatch")
        expected = compute_c3_semantic_digest(
            scope=self.scope,
            plan=self.plan,
            policy_fingerprint=self.policy_fingerprint,
            source_observations=self.source_observations,
            resolved_subjects=self.resolved_subjects,
            facts=self.facts,
            relationships=self.relationships,
            evidence=self.evidence,
            unresolved=self.unresolved,
            conflicts=self.conflicts,
            rationales=self.rationales,
            coverage=self.coverage,
            omissions=self.omissions,
            limits_and_usage=self.limits_and_usage,
            outcome=self.outcome,
        )
        if self.semantic_digest != expected:
            raise ValueError("Bundle semantic digest mismatch")
        return self


class EvidenceRequest(C3Model):
    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )
    project_id: UUID
    architecture_version_id: UUID
    entity_ids: tuple[UUID, ...] = ()
    relationship_ids: tuple[UUID, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    limit: int = Field(default=DEFAULT_RETRIEVAL_LIMIT, ge=1, le=MAX_RETRIEVAL_LIMIT)
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)

    @model_validator(mode="after")
    def selector_exclusivity(self) -> Self:
        if (
            sum(
                bool(x)
                for x in (self.entity_ids, self.relationship_ids, self.evidence_ids)
            )
            > 1
        ):
            raise ValueError("Use only one evidence selector family")
        return self


# --- Consumer Protocols (§7A.3) ---


class KnowledgeQueryPort(Protocol):
    """M3 query port protocol for controlled retrieval operations."""

    def query(
        self,
        request: KnowledgeQueryRequest,
        *,
        principal: RetrievalPrincipal,
    ) -> KnowledgeQueryResponse: ...


class ContextReadPort(Protocol):
    def build_context(
        self, request: ContextRequest, *, principal: RetrievalPrincipal
    ) -> ContextBundle: ...


class EvidenceReadPort(Protocol):
    def read_evidence(
        self, request: EvidenceRequest, *, principal: RetrievalPrincipal
    ) -> EvidencePage: ...


class CanonicalReadPort(Protocol):
    """M3 port for bounded read access to canonical Architecture Model collections."""

    def get_version(self, version_id: UUID, project_id: UUID) -> RetrievalScope: ...

    def get_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> CanonicalFactView | None: ...

    def list_entities(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> tuple[tuple[CanonicalFactView, ...], int]: ...

    def list_relationships(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> tuple[tuple[RelationshipView, ...], int]: ...

    def list_evidence(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        entity_id: UUID | None = None,
    ) -> tuple[tuple[EvidenceItemView, ...], int]: ...

    def list_unresolved(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[tuple[UnresolvedView, ...], int]: ...

    def list_conflicts(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[tuple[ConflictView, ...], int]: ...


class GraphReadPort(Protocol):
    """M3 port for bounded read access to the projected architecture graph."""

    def resolve_active_generation(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        *,
        timeout_seconds: float,
    ) -> Any: ...

    def verify_generation_still_active(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        *,
        timeout_seconds: float,
    ) -> bool: ...

    def get_neighborhood(self, request: Any) -> Any: ...

    def get_dependencies(self, request: Any) -> Any: ...

    def get_dependents(self, request: Any) -> Any: ...

    def get_containment(self, request: Any) -> Any: ...

    def get_bounded_paths(self, request: Any) -> Any: ...


__all__ = [
    "C3_CONTRACT_VERSION",
    "DEFAULT_RETRIEVAL_LIMIT",
    "MAX_CURSOR_LENGTH",
    "MAX_LOGICAL_ID_LENGTH",
    "MAX_QUERY_STRING_LENGTH",
    "MAX_RETRIEVAL_LIMIT",
    "CanonicalFactView",
    "CanonicalReadPort",
    "CanonicalPathView",
    "ConflictView",
    "ContainmentDirection",
    "ContextBundle",
    "ContextRequest",
    "ContextReadPort",
    "Coverage",
    "EvidenceItemView",
    "EvidencePage",
    "EvidenceRequest",
    "EvidenceReadPort",
    "FreshnessState",
    "GraphReadPort",
    "KnowledgeQueryPort",
    "KnowledgeQueryRequest",
    "KnowledgeQueryResponse",
    "LimitsAndUsage",
    "OmissionSummary",
    "RecordKind",
    "RelationshipView",
    "ResolutionState",
    "ResolvedSubject",
    "RetrievalCapacityExceededError",
    "RetrievalCursorExpiredError",
    "RetrievalCursorInvalidError",
    "RetrievalDeadlineExceededError",
    "RetrievalError",
    "RetrievalGenerationChangedError",
    "RetrievalIntegrityFailedError",
    "RetrievalInvalidRequestError",
    "RetrievalNotFoundError",
    "RetrievalOperation",
    "RetrievalOutcome",
    "RetrievalPlan",
    "RetrievalPrincipal",
    "RetrievalScope",
    "RetrievalUnavailableError",
    "SelectionRationale",
    "SelectionRationaleCode",
    "SelectorType",
    "SourceKind",
    "SourceObservation",
    "SubjectCandidate",
    "SubjectSelector",
    "TraversalDirection",
    "UnresolvedView",
]
