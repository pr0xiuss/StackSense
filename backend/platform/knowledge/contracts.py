"""P5-C1 search request, hit, page, status, and error contracts.

This module defines the transport-neutral C1 candidate contracts for Phase 5
Module 2 (Knowledge Projection and Search Index), adhering to §7.8 and §7.12.3
of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

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

from backend.platform.analysis.architecture.model import (
    ArchitectureEntityKind,
    ArchitectureFactStatus,
)
from backend.platform.delivery.contracts import (
    ArtifactReference,
    Digest,
    VersionScope,
)
from backend.platform.knowledge.model import (
    C1_CONTRACT_VERSION,
    KnowledgeDocumentKind,
    SourceReferenceDescriptor,
)

DEFAULT_SEARCH_LIMIT: Final[int] = 25
MAX_SEARCH_LIMIT: Final[int] = 100
DEFAULT_SEARCH_TIMEOUT_SECONDS: Final[float] = 2.0
MAX_SEARCH_TIMEOUT_SECONDS: Final[float] = 5.0
MAX_SEARCH_QUERY_LENGTH: Final[int] = 500
MAX_SEARCH_CURSOR_LENGTH: Final[int] = 2048
SearchResourceState = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "STALE"]
SearchFreshness = Literal[
    "CURRENT", "STALE", "BUILDING", "FAILED", "UNAVAILABLE", "UNKNOWN"
]


# --- Error Taxonomy (§7.8) ---


class SearchError(Exception):
    """Base exception for all safe M2 knowledge and search errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.safe_details = dict(safe_details) if safe_details else {}


class SearchNotReadyError(SearchError):
    """Search projection has no readable active generation."""

    def __init__(
        self,
        message: str = "Search projection is not ready for queries",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="search_not_ready", safe_details=safe_details)


class SearchGenerationChangedError(SearchError):
    """Active projection generation changed during read or continuation."""

    def __init__(
        self,
        message: str = "Active search generation has changed; please restart query",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, code="search_generation_changed", safe_details=safe_details
        )


class SearchCursorExpiredError(SearchError):
    """Pagination cursor or point-in-time handle expired."""

    def __init__(
        self,
        message: str = "Search pagination cursor has expired",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, code="search_cursor_expired", safe_details=safe_details
        )


class SearchCursorInvalidError(SearchError):
    """Pagination cursor is malformed, tampered, or mis-scoped."""

    def __init__(
        self,
        message: str = "Search pagination cursor is invalid",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, code="search_cursor_invalid", safe_details=safe_details
        )


class SearchIntegrityError(SearchError):
    """Referential, key set, count, or digest verification invariant violated."""

    def __init__(
        self,
        message: str = "Search integrity verification failed",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, code="search_integrity_failed", safe_details=safe_details
        )


class SearchCapacityExceededError(SearchError):
    """Request or model exceeds approved resource, document, or byte limits."""

    def __init__(
        self,
        message: str = "Search capacity limit exceeded",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, code="search_capacity_exceeded", safe_details=safe_details
        )


class SearchBackendUnavailableError(SearchError):
    """Elasticsearch or storage dependency is unreachable or unhealthy."""

    def __init__(
        self,
        message: str = "Search storage backend is unavailable",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, code="search_backend_unavailable", safe_details=safe_details
        )


class SearchDeadlineExceededError(SearchError):
    """Whole-operation monotonic deadline exhausted."""

    def __init__(
        self,
        message: str = "Search operation deadline exceeded",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, code="search_deadline_exceeded", safe_details=safe_details
        )


class SearchCapabilityUnavailableError(SearchError):
    """Requested search mode or capability is not available or disabled."""

    def __init__(
        self,
        message: str = "Requested search capability is unavailable",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, code="search_capability_unavailable", safe_details=safe_details
        )


# --- DTOs and Capabilities (§7.8, §7.12.3) ---


class CapabilityState(StrEnum):
    """Closed state vocabulary for search capability flags."""

    AVAILABLE = "available"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class SearchCapabilities(BaseModel):
    """Explicit capability advertising for lexical, semantic, and hybrid search."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    lexical: CapabilityState = CapabilityState.AVAILABLE
    semantic: CapabilityState = CapabilityState.UNAVAILABLE
    hybrid: CapabilityState = CapabilityState.UNAVAILABLE
    semantic_reason: str = "provider_not_approved"
    hybrid_reason: str = "provider_not_approved"


class SearchRequest(BaseModel):
    """Request DTO for scoped lexical search over an Architecture Version."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    project_id: UUID
    architecture_version_id: UUID
    q: str = Field(min_length=1, max_length=MAX_SEARCH_QUERY_LENGTH, pattern=r"\S")
    mode: Literal["lexical"] = "lexical"
    document_kinds: tuple[KnowledgeDocumentKind, ...] | None = None
    entity_kinds: tuple[str, ...] | None = None
    statuses: tuple[str, ...] | None = None
    limit: int = Field(default=DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_LIMIT)
    cursor: str | None = Field(default=None, max_length=MAX_SEARCH_CURSOR_LENGTH)
    timeout_seconds: float = Field(
        default=DEFAULT_SEARCH_TIMEOUT_SECONDS, gt=0, le=MAX_SEARCH_TIMEOUT_SECONDS
    )

    @field_validator("entity_kinds", "statuses")
    @classmethod
    def allowed_filters(
        cls, value: tuple[str, ...] | None, info: Any
    ) -> tuple[str, ...] | None:
        if value is None:
            return None
        allowed = {
            item.value
            for item in (
                ArchitectureEntityKind
                if info.field_name == "entity_kinds"
                else ArchitectureFactStatus
            )
        }
        if set(value) - allowed:
            raise ValueError("Unsupported canonical search filter")
        return tuple(sorted(set(value)))

    @field_validator("document_kinds")
    @classmethod
    def sorted_document_kinds(
        cls, value: tuple[KnowledgeDocumentKind, ...] | None
    ) -> tuple[KnowledgeDocumentKind, ...] | None:
        return tuple(sorted(set(value))) if value is not None else None


class SearchHit(BaseModel):
    """Search hit representing an exact matching knowledge record."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    knowledge_key: Digest
    document_kind: KnowledgeDocumentKind
    canonical_reference: str
    title: str
    kind: str | None = None
    status: str | None = None
    source_logical_id: str | None = None
    target_logical_id: str | None = None
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_reference: SourceReferenceDescriptor | None = None
    rank_tier: int = Field(
        default=2, ge=1, le=2
    )  # 1 = exact canonical/name match, 2 = text match
    score: float = Field(ge=0.0, allow_inf_nan=False)
    scope: VersionScope


class SearchPage(BaseModel):
    """Candidate C1 v1 page identifying its exact selected generation/index.

    The index UUID is an opaque, non-secret equality token, never an input
    selector or storage locator. Physical index names and credentials stay private.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    c1_version: Literal["1.0.0"] = C1_CONTRACT_VERSION
    scope: VersionScope
    generation_id: UUID
    index_uuid: str = Field(min_length=1)
    items: tuple[SearchHit, ...]
    total_hits: int = Field(ge=0)
    has_more: bool
    next_cursor: str | None = None
    capabilities: SearchCapabilities = Field(default_factory=SearchCapabilities)

    @model_validator(mode="after")
    def consistent_page(self) -> Self:
        if any(item.scope != self.scope for item in self.items):
            raise ValueError("Search hits must match the exact page scope")
        if len({item.knowledge_key for item in self.items}) != len(self.items):
            raise ValueError("Duplicate knowledge keys in search page")
        if self.total_hits < len(self.items):
            raise ValueError("Search total cannot be smaller than page size")
        if self.has_more != bool(self.next_cursor) or (
            self.has_more and not self.items
        ):
            raise ValueError("Search continuation must match nonempty page state")
        return self


class SearchStatus(BaseModel):
    """Orthogonal freshness and visibility projection for an Architecture Version."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    scope: VersionScope
    resource_state: SearchResourceState
    freshness: SearchFreshness
    active_reference: ArtifactReference | None = None
    attempt_state: str | None = None
    is_readable: bool = False
    is_current_version: bool | None = None
    last_verified_at: AwareDatetime | None = None
    last_failure_code: str | None = None
    capabilities: SearchCapabilities = Field(default_factory=SearchCapabilities)
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def consistent_reference(self) -> Self:
        if (
            self.active_reference is not None
            and self.active_reference.scope != self.scope
        ):
            raise ValueError("Search status reference must match its exact scope")
        return self


class SearchReadPort(Protocol):
    """M3 read seam; caller authorizes exact project/version and supplies actor.

    Cursor is opaque and bound to that actor and the original request. Never
    instantiate producer repositories/ES clients or interpret storage identities.
    Evidence expansion uses canonical public APIs, not this lexical index.
    First page selects the accepted active generation of the exact version;
    continuation pins it and exposes the same generation_id/index_uuid pair.
    Pointer drift, generation/index loss or expired continuation fails explicitly;
    there is no silent restart or historical-generation selector. Consumers
    combining independent searches compare scope/generation/index and reject
    mixed-generation results. Semantic/hybrid are unavailable, not fallback modes.
    """

    def search(self, request: SearchRequest, *, actor_id: UUID) -> SearchPage: ...


class SearchStatusPort(Protocol):
    """Read-only freshness/capability seam independent of M1 work mutation."""

    def get_status(
        self, project_id: UUID, architecture_version_id: UUID
    ) -> SearchStatus: ...


class ResolvedSearchGeneration(BaseModel):
    """Resolution of committed ArtifactReference and physical index identity."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    reference: ArtifactReference
    index_name: str
    index_uuid: str
    generation_id: UUID


__all__ = [
    "DEFAULT_SEARCH_LIMIT",
    "DEFAULT_SEARCH_TIMEOUT_SECONDS",
    "MAX_SEARCH_CURSOR_LENGTH",
    "MAX_SEARCH_LIMIT",
    "MAX_SEARCH_QUERY_LENGTH",
    "MAX_SEARCH_TIMEOUT_SECONDS",
    "CapabilityState",
    "ResolvedSearchGeneration",
    "SearchBackendUnavailableError",
    "SearchCapabilities",
    "SearchCapabilityUnavailableError",
    "SearchCapacityExceededError",
    "SearchCursorExpiredError",
    "SearchCursorInvalidError",
    "SearchDeadlineExceededError",
    "SearchError",
    "SearchGenerationChangedError",
    "SearchHit",
    "SearchIntegrityError",
    "SearchNotReadyError",
    "SearchPage",
    "SearchRequest",
    "SearchReadPort",
    "SearchResourceState",
    "SearchFreshness",
    "SearchStatus",
    "SearchStatusPort",
]
