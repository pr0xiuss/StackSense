"""P5-C3 retrieval planning, resolution, operation execution, and cursor management.

This module implements the core KnowledgeQueryService and RetrievalPlanner
foundation for Phase 5 Module 3, adhering to §7A.4, §7A.5, §7A.6, and §7A.11
of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError

from backend.platform.graph.query_contracts import (
    APPROVED_DEPENDENCY_RELATIONSHIP_KINDS,
    BoundedPathsRequest,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphRelationshipKind,
)
from backend.platform.graph.query_contracts import (
    ContainmentDirection as P4ContainmentDirection,
)
from backend.platform.knowledge.contracts import (
    SearchReadPort,
    SearchRequest,
)
from backend.platform.knowledge.model import KnowledgeDocumentKind
from backend.platform.knowledge.retrieval_adapters import (
    SearchReadAdapter,
)
from backend.platform.knowledge.retrieval_configuration import (
    RetrievalBudget,
    RetrievalPolicy,
    operation_budget,
)
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalFactView,
    CanonicalPathView,
    CanonicalReadPort,
    ConflictView,
    ContextBundle,
    ContextRequest,
    Coverage,
    EvidenceItemView,
    EvidencePage,
    EvidenceRequest,
    FreshnessState,
    GraphReadPort,
    KnowledgeQueryPort,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    OmissionSummary,
    RecordKind,
    RelationshipView,
    ResolutionState,
    ResolvedSubject,
    RetrievalCapacityExceededError,
    RetrievalCursorExpiredError,
    RetrievalCursorInvalidError,
    RetrievalGenerationChangedError,
    RetrievalIntegrityFailedError,
    RetrievalInvalidRequestError,
    RetrievalNotFoundError,
    RetrievalOperation,
    RetrievalOutcome,
    RetrievalPlan,
    RetrievalPrincipal,
    RetrievalScope,
    RetrievalUnavailableError,
    SelectionRationale,
    SelectionRationaleCode,
    SourceKind,
    SourceObservation,
    SubjectCandidate,
    SubjectSelector,
    TraversalDirection,
    UnresolvedView,
)

_TOKEN_VERSION = "1.0.0"


# --- Cursor Token Envelope Helpers (§7A.6) ---


def _compute_request_fingerprint(request: KnowledgeQueryRequest) -> str:
    """Bind every original selector, expected scope and operation parameter."""
    canonical = json.dumps(
        request.model_dump(mode="json", exclude={"cursor"}),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def encode_c3_cursor(
    *,
    secret_key: str,
    principal: RetrievalPrincipal,
    scope: RetrievalScope,
    request: KnowledgeQueryRequest,
    policy: RetrievalPolicy,
    scan_position: int,
    chain_page: int,
    chain_work_units: int,
    search_generation_id: UUID | None = None,
    search_index_uuid: str | None = None,
    graph_generation_id: UUID | None = None,
    upstream_cursor: str | None = None,
    ttl_seconds: float,
    issued_at: float | None = None,
    expires_at: float | None = None,
) -> str:
    """Encode stateless HMAC-signed C3 continuation cursor (§7A.6)."""
    now = time.time()
    payload = {
        "v": _TOKEN_VERSION,
        "kid": "c3-k1",
        "act": str(principal.actor_id),
        "prj": str(scope.project_id),
        "ver": str(scope.architecture_version_id),
        "dig": scope.canonical_digest,
        "op": request.operation.value,
        "rfp": _compute_request_fingerprint(request),
        "pfp": policy.compute_fingerprint(),
        "pos": scan_position,
        "cp": chain_page,
        "cwu": chain_work_units,
        "iat": issued_at if issued_at is not None else now,
        "exp": expires_at if expires_at is not None else now + ttl_seconds,
        "s_gen": str(search_generation_id) if search_generation_id else None,
        "s_idx": search_index_uuid,
        "g_gen": str(graph_generation_id) if graph_generation_id else None,
        "upc": upstream_cursor,
    }
    raw_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    raw_bytes = raw_json.encode("utf-8")
    sig = hmac.new(secret_key.encode("utf-8"), raw_bytes, hashlib.sha256).digest()
    envelope = {
        "d": base64.urlsafe_b64encode(raw_bytes).decode("ascii"),
        "s": base64.urlsafe_b64encode(sig).decode("ascii"),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(envelope, separators=(",", ":")).encode("ascii")
    ).decode("ascii")
    if len(encoded) > policy.max_cursor_bytes:
        raise RetrievalCapacityExceededError(
            f"Encoded cursor exceeds maximum byte budget "
            f"({len(encoded)} > {policy.max_cursor_bytes})"
        )
    return encoded


def decode_c3_cursor(
    cursor: str,
    *,
    secret_key: str,
    principal: RetrievalPrincipal,
    scope: RetrievalScope | None,
    request: KnowledgeQueryRequest,
    policy: RetrievalPolicy,
) -> dict[str, Any]:
    """Validate and decode stateless HMAC-signed C3 cursor (§7A.6)."""
    if len(cursor) > policy.max_cursor_bytes:
        raise RetrievalCursorInvalidError(
            "Cursor length exceeds maximum allowed byte budget"
        )

    try:

        def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate cursor field")
                result[key] = value
            return result

        raw_env = base64.b64decode(
            cursor.encode("ascii"), altchars=b"-_", validate=True
        )
        envelope = json.loads(raw_env, object_pairs_hook=closed_object)
        if not isinstance(envelope, dict) or set(envelope) != {"d", "s"}:
            raise ValueError("Invalid envelope")
        data_bytes = base64.urlsafe_b64decode(envelope["d"].encode("ascii"))
        provided_sig = base64.urlsafe_b64decode(envelope["s"].encode("ascii"))
    except Exception as exc:
        raise RetrievalCursorInvalidError(
            "Malformed cursor encoding or envelope"
        ) from exc

    expected_sig = hmac.new(
        secret_key.encode("utf-8"), data_bytes, hashlib.sha256
    ).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise RetrievalCursorInvalidError("Cursor HMAC signature verification failed")

    try:
        payload = json.loads(data_bytes, object_pairs_hook=closed_object)
        fields = {
            "v",
            "kid",
            "act",
            "prj",
            "ver",
            "dig",
            "op",
            "rfp",
            "pfp",
            "pos",
            "cp",
            "cwu",
            "iat",
            "exp",
            "s_gen",
            "s_idx",
            "g_gen",
            "upc",
        }
        if (
            not isinstance(payload, dict)
            or set(payload) != fields
            or payload["kid"] != "c3-k1"
        ):
            raise ValueError("Invalid cursor shape")
        for key in ("pos", "cp", "cwu"):
            if type(payload[key]) is not int or payload[key] < 0:
                raise ValueError("Invalid counter")
        import math

        for key in ("iat", "exp"):
            if type(payload[key]) not in (int, float) or not math.isfinite(
                payload[key]
            ):
                raise ValueError("Invalid timestamp")
        if (
            payload["exp"] <= payload["iat"]
            or payload["exp"] - payload["iat"] > policy.cursor_ttl_seconds
        ):
            raise ValueError("Invalid lifetime")
        if bool(payload["s_gen"]) != bool(payload["s_idx"]):
            raise ValueError("Incomplete source binding")
        for key in ("s_gen", "g_gen"):
            if payload[key] is not None:
                UUID(payload[key])
        for key in ("s_idx", "upc"):
            if payload[key] is not None and not isinstance(payload[key], str):
                raise ValueError("Invalid opaque binding")
    except Exception as exc:
        raise RetrievalCursorInvalidError("Malformed cursor JSON payload") from exc

    # Enforce exact version and parameter binding
    if payload.get("v") != _TOKEN_VERSION:
        raise RetrievalCursorInvalidError("Unsupported cursor token version")
    if payload.get("act") != str(principal.actor_id):
        raise RetrievalCursorInvalidError("Cursor actor binding mismatch")
    if payload.get("prj") != str(request.project_id):
        raise RetrievalCursorInvalidError("Cursor project binding mismatch")
    if payload.get("ver") != str(request.architecture_version_id):
        raise RetrievalCursorInvalidError(
            "Cursor architecture version binding mismatch"
        )
    if scope is not None and payload.get("dig") != scope.canonical_digest:
        raise RetrievalCursorInvalidError("Cursor canonical digest binding mismatch")
    if payload.get("op") != request.operation.value:
        raise RetrievalCursorInvalidError("Cursor operation mismatch")
    if payload.get("rfp") != _compute_request_fingerprint(request):
        raise RetrievalCursorInvalidError("Cursor request fingerprint mismatch")
    if payload.get("pfp") != policy.compute_fingerprint():
        raise RetrievalCursorInvalidError("Cursor policy fingerprint mismatch")

    # Expiry verification
    now = time.time()
    if now > float(payload.get("exp", 0)):
        raise RetrievalCursorExpiredError("Retrieval cursor has expired")

    # Chain bounds verification
    chain_page = int(payload.get("cp", 1))
    chain_work_units = int(payload.get("cwu", 0))
    if chain_page > policy.max_chain_pages:
        raise RetrievalCapacityExceededError(
            f"Continuation exceeds maximum chain pages "
            f"({chain_page} > {policy.max_chain_pages})"
        )
    if chain_work_units > policy.max_chain_work_units:
        raise RetrievalCapacityExceededError(
            f"Continuation exceeds maximum chain work units "
            f"({chain_work_units} > {policy.max_chain_work_units})"
        )

    assert isinstance(payload, dict)
    return payload


# --- Subject Resolution (§7A.5) ---


def resolve_subject(
    selector: SubjectSelector,
    canonical_port: CanonicalReadPort,
    version_id: UUID,
    project_id: UUID,
    *,
    max_scan_rows: int,
    max_candidates: int = 100,
    page_size: int = 100,
) -> ResolvedSubject:
    """Deterministically resolve a SubjectSelector to a canonical entity or item.

    Adheres to §7A.5.
    """
    if selector.selector_type == "record_id":
        assert selector.record_id is not None
        if selector.record_kind == "entity":
            fact = canonical_port.get_entity(version_id, selector.record_id, project_id)
            if fact:
                cand = SubjectCandidate(
                    record_id=fact.record_id,
                    logical_id=fact.logical_id,
                    kind=fact.kind,
                    name=fact.name,
                    namespace=fact.namespace,
                    reason="exact_record_id",
                )
                return ResolvedSubject(
                    selector=selector,
                    state=ResolutionState.RESOLVED,
                    selected_id=fact.record_id,
                    selected_logical_id=fact.logical_id,
                    selected_kind=fact.kind,
                    candidates=(cand,),
                    scan_complete=True,
                )
            return ResolvedSubject(
                selector=selector,
                state=ResolutionState.NOT_FOUND,
                candidates=(),
                scan_complete=True,
            )

        # For non-entity record kinds, scan the collection by record_id
        items: list[Any] = []
        offset = 0
        limit = min(page_size, 100, max_scan_rows)
        scanned = 0
        while scanned < max_scan_rows:
            limit = min(limit, max_scan_rows - scanned)
            batch, total = _list_collection_by_kind(
                canonical_port,
                selector.record_kind,
                version_id,
                project_id,
                limit=limit,
                offset=offset,
            )
            for item in batch:
                if item.record_id == selector.record_id:
                    cand = SubjectCandidate(
                        record_id=item.record_id,
                        logical_id=item.logical_id,
                        kind=selector.record_kind,
                        reason="exact_record_id",
                    )
                    return ResolvedSubject(
                        selector=selector,
                        state=ResolutionState.RESOLVED,
                        selected_id=item.record_id,
                        selected_logical_id=item.logical_id,
                        selected_kind=selector.record_kind,
                        candidates=(cand,),
                        scan_complete=True,
                    )
            scanned += len(batch)
            offset += len(batch)
            if scanned >= total or not batch:
                return ResolvedSubject(
                    selector=selector,
                    state=ResolutionState.NOT_FOUND,
                    candidates=(),
                    scan_complete=True,
                )
        return ResolvedSubject(
            selector=selector,
            state=ResolutionState.INCOMPLETE,
            candidates=(),
            scan_complete=False,
        )

    elif selector.selector_type == "logical_id":
        assert selector.logical_id is not None
        offset = 0
        limit = min(page_size, 100, max_scan_rows)
        scanned = 0
        matched: list[SubjectCandidate] = []
        while scanned < max_scan_rows:
            limit = min(limit, max_scan_rows - scanned)
            batch, total = _list_collection_by_kind(
                canonical_port,
                selector.record_kind,
                version_id,
                project_id,
                limit=limit,
                offset=offset,
            )
            for item in batch:
                if item.logical_id == selector.logical_id:
                    if len(matched) >= max_candidates:
                        raise RetrievalCapacityExceededError(
                            "Candidate budget exceeded"
                        )
                    matched.append(
                        SubjectCandidate(
                            record_id=item.record_id,
                            logical_id=item.logical_id,
                            kind=selector.record_kind,
                            name=getattr(item, "name", None),
                            namespace=getattr(item, "namespace", None),
                            reason="exact_logical_id",
                        )
                    )
            scanned += len(batch)
            offset += len(batch)
            if scanned >= total or not batch:
                break

        scan_complete = (scanned >= total) if "total" in locals() else True

        if len(matched) == 1 and scan_complete:
            m = matched[0]
            return ResolvedSubject(
                selector=selector,
                state=ResolutionState.RESOLVED,
                selected_id=m.record_id,
                selected_logical_id=m.logical_id,
                selected_kind=m.kind,
                candidates=tuple(matched),
                scan_complete=True,
            )
        elif len(matched) > 1:
            # Sort candidates by canonical logical_id and UUID
            sorted_candidates = tuple(
                sorted(matched, key=lambda c: (c.logical_id, str(c.record_id)))
            )
            return ResolvedSubject(
                selector=selector,
                state=ResolutionState.AMBIGUOUS,
                candidates=sorted_candidates,
                scan_complete=scan_complete,
            )
        elif not scan_complete:
            return ResolvedSubject(
                selector=selector,
                state=ResolutionState.INCOMPLETE,
                candidates=tuple(matched),
                scan_complete=False,
            )
        else:
            return ResolvedSubject(
                selector=selector,
                state=ResolutionState.NOT_FOUND,
                candidates=(),
                scan_complete=True,
            )

    elif selector.selector_type == "entity_name":
        assert selector.name is not None
        offset = 0
        limit = min(page_size, 100, max_scan_rows)
        scanned = 0
        matched_named: list[SubjectCandidate] = []
        total = 0
        while scanned < max_scan_rows:
            limit = min(limit, max_scan_rows - scanned)
            batch, total = canonical_port.list_entities(
                version_id, project_id, limit=limit, offset=offset
            )
            for item in batch:
                # Name matching (with optional namespace constraint)
                if item.name == selector.name:
                    if (
                        selector.namespace is None
                        or item.namespace == selector.namespace
                    ):
                        if len(matched_named) >= max_candidates:
                            raise RetrievalCapacityExceededError(
                                "Candidate budget exceeded"
                            )
                        matched_named.append(
                            SubjectCandidate(
                                record_id=item.record_id,
                                logical_id=item.logical_id,
                                kind=item.kind,
                                name=item.name,
                                namespace=item.namespace,
                                reason="exact_name",
                            )
                        )
            scanned += len(batch)
            offset += len(batch)
            if scanned >= total or not batch:
                break

        scan_complete = scanned >= total

        if len(matched_named) == 1 and scan_complete:
            m = matched_named[0]
            return ResolvedSubject(
                selector=selector,
                state=ResolutionState.RESOLVED,
                selected_id=m.record_id,
                selected_logical_id=m.logical_id,
                selected_kind=m.kind,
                candidates=tuple(matched_named),
                scan_complete=True,
            )
        elif len(matched_named) > 1:
            sorted_candidates = tuple(
                sorted(matched_named, key=lambda c: (c.logical_id, str(c.record_id)))
            )
            return ResolvedSubject(
                selector=selector,
                state=ResolutionState.AMBIGUOUS,
                candidates=sorted_candidates,
                scan_complete=scan_complete,
            )
        elif not scan_complete:
            return ResolvedSubject(
                selector=selector,
                state=ResolutionState.INCOMPLETE,
                candidates=tuple(matched_named),
                scan_complete=False,
            )
        else:
            return ResolvedSubject(
                selector=selector,
                state=ResolutionState.NOT_FOUND,
                candidates=(),
                scan_complete=True,
            )

    raise RetrievalInvalidRequestError(
        f"Unsupported selector type: {selector.selector_type}"
    )


def _list_collection_by_kind(
    canonical_port: CanonicalReadPort,
    record_kind: str,
    version_id: UUID,
    project_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[tuple[Any, ...], int]:
    if record_kind == "entity":
        return canonical_port.list_entities(
            version_id, project_id, limit=limit, offset=offset
        )
    elif record_kind == "relationship":
        return canonical_port.list_relationships(
            version_id, project_id, limit=limit, offset=offset
        )
    elif record_kind == "evidence":
        return canonical_port.list_evidence(
            version_id, project_id, limit=limit, offset=offset
        )
    elif record_kind == "unresolved":
        return canonical_port.list_unresolved(
            version_id, project_id, limit=limit, offset=offset
        )
    elif record_kind == "conflict":
        return canonical_port.list_conflicts(
            version_id, project_id, limit=limit, offset=offset
        )
    raise RetrievalInvalidRequestError(f"Unknown record_kind: {record_kind}")


# --- KnowledgeQueryService Implementation (§7A.3, §7A.4) ---


class _CanonicalCalls:
    """Bounded validation around public canonical methods; no persistence access."""

    def __init__(self, port: CanonicalReadPort, budget: RetrievalBudget) -> None:
        self.port, self.budget = port, budget
        self.final = False

    @staticmethod
    def _validated(model: type[BaseModel], value: Any) -> BaseModel:
        try:
            return model.model_validate(value)
        except ValidationError:
            raise RetrievalIntegrityFailedError("Invalid canonical response") from None

    def __getattr__(self, name: str) -> Any:
        function = getattr(self.port, name)

        def call(*args: Any, **kwargs: Any) -> Any:
            self.budget.call("canonical", final=self.final)
            result = function(*args, **kwargs)
            if name.startswith("list_"):
                items, total = result
                if total < len(items) or len(items) > kwargs["limit"]:
                    raise RetrievalIntegrityFailedError("Invalid canonical page")
                kind = name.removeprefix("list_")
                self.budget.scanned(kind, len(items))
                models: dict[str, type[BaseModel]] = {
                    "entities": CanonicalFactView,
                    "relationships": RelationshipView,
                    "evidence": EvidenceItemView,
                    "unresolved": UnresolvedView,
                    "conflicts": ConflictView,
                }
                result = tuple(self._validated(models[kind], x) for x in items), total
            elif name == "get_version":
                result = self._validated(RetrievalScope, result)
            elif result is not None:
                result = self._validated(CanonicalFactView, result)
            self.budget.remaining(reserve=not self.final)
            return result

        return call


class KnowledgeQueryService(KnowledgeQueryPort):
    """Read-only C3 composition. Every public method owns one bounded operation."""

    def __init__(
        self,
        canonical_port: CanonicalReadPort,
        *,
        search_port: SearchReadPort | None = None,
        graph_port: GraphReadPort | None = None,
        policy: RetrievalPolicy,
        cursor_secret_key: str,
        search_factory: Callable[[], SearchReadPort | None] | None = None,
        graph_factory: Callable[[], GraphReadPort | None] | None = None,
    ) -> None:
        self._canonical_port, self._policy = canonical_port, policy
        self._search_port, self._graph_port = search_port, graph_port
        self._search_factory, self._graph_factory = search_factory, graph_factory
        if len(cursor_secret_key.encode()) < 32:
            raise RetrievalUnavailableError("Dedicated retrieval cursor key required")
        self._cursor_secret_key = cursor_secret_key

    def _validate_request(self, request: KnowledgeQueryRequest) -> None:
        p = self._policy
        if request.q is not None and (
            not request.q.strip() or len(request.q.encode()) > p.max_query_bytes
        ):
            raise RetrievalInvalidRequestError("Invalid literal query")
        if request.limit > p.canonical_page_size:
            raise RetrievalCapacityExceededError(
                "Requested page exceeds operating policy"
            )
        if (
            len(request.document_kinds) + len(request.relationship_kinds)
            > p.max_filters
        ):
            raise RetrievalCapacityExceededError("Filter budget exceeded")
        if request.graph_depth is not None and request.graph_depth > p.max_graph_depth:
            raise RetrievalCapacityExceededError("Graph depth exceeds operating policy")
        if set(request.document_kinds) - {x.value for x in KnowledgeDocumentKind}:
            raise RetrievalInvalidRequestError("Unsupported document kind")
        if set(request.relationship_kinds) - {x.value for x in GraphRelationshipKind}:
            raise RetrievalInvalidRequestError("Unsupported relationship kind")
        if request.relationship_kinds and request.operation not in (
            RetrievalOperation.RELATIONSHIPS,
            RetrievalOperation.DEPENDENCIES,
            RetrievalOperation.DEPENDENTS,
            RetrievalOperation.PATHS,
        ):
            raise RetrievalInvalidRequestError(
                "Relationship filter is unsupported for this operation"
            )
        if request.document_kinds and (
            request.operation != RetrievalOperation.LOOKUP or not request.q
        ):
            raise RetrievalInvalidRequestError(
                "Document kinds require a lexical lookup"
            )
        if request.operation == RetrievalOperation.PATHS and request.cursor:
            raise RetrievalInvalidRequestError("Paths are non-paginated")
        for selector in (request.subject, request.target):
            if selector:
                for value in (
                    selector.logical_id,
                    selector.name,
                    *(selector.namespace or ()),
                ):
                    if value and len(value.encode()) > p.max_identifier_bytes:
                        raise RetrievalCapacityExceededError(
                            "Identifier budget exceeded"
                        )

    def _begin(
        self,
        version: UUID,
        project: UUID,
        principal: RetrievalPrincipal,
        budget: RetrievalBudget,
    ) -> tuple[_CanonicalCalls, RetrievalScope]:
        if principal.project_id != project:
            raise RetrievalInvalidRequestError("Principal project mismatch")
        calls = _CanonicalCalls(self._canonical_port, budget)
        scope = calls.get_version(version, project)
        if scope.project_id != project or scope.architecture_version_id != version:
            raise RetrievalIntegrityFailedError("Canonical header scope mismatch")
        if (
            scope.architecture_schema_version != "1.0.0"
            or scope.ir_schema_version != "1.0.0"
        ):
            raise RetrievalUnavailableError("Canonical schema is not supported")
        return calls, scope

    @staticmethod
    def _source_scope(actual: Any, scope: RetrievalScope) -> None:
        for key in (
            "project_id",
            "architecture_version_id",
            "repository_id",
            "analysis_id",
            "snapshot_id",
            "canonical_digest",
            "sequence_number",
            "architecture_schema_version",
            "ir_schema_version",
        ):
            if hasattr(actual, key) and getattr(actual, key) != getattr(scope, key):
                raise RetrievalIntegrityFailedError("Source scope mismatch")

    def _execute(
        self,
        request: KnowledgeQueryRequest,
        principal: RetrievalPrincipal,
        calls: _CanonicalCalls,
        scope: RetrievalScope,
        budget: RetrievalBudget,
        search: SearchReadAdapter | None,
        graph: GraphReadPort | None,
        state: dict[str, Any],
    ) -> KnowledgeQueryResponse:
        self._validate_request(request)
        canonical = cast(CanonicalReadPort, calls)
        p = self._policy
        position = state.get("pos", 0)
        subjects = [
            (
                resolve_subject(
                    s,
                    canonical,
                    scope.architecture_version_id,
                    scope.project_id,
                    max_scan_rows=p.canonical_max_rows_per_collection,
                    max_candidates=p.max_retained_candidates,
                    page_size=p.canonical_page_size,
                )
                if s
                else None
            )
            for s in (request.subject, request.target)
        ]
        subject, target = subjects
        if any(s and len(s.candidates) > p.max_retained_candidates for s in subjects):
            raise RetrievalCapacityExceededError("Candidate budget exceeded")
        facts: list[CanonicalFactView] = []
        relationships: list[RelationshipView] = []
        evidence: list[EvidenceItemView] = []
        unresolved: list[UnresolvedView] = []
        conflicts: list[ConflictView] = []
        paths: list[CanonicalPathView] = []
        observations: list[SourceObservation] = [
            SourceObservation(
                source_kind=SourceKind.CANONICAL,
                contract_version=scope.architecture_schema_version,
                scope=scope,
                freshness=FreshnessState.UNKNOWN,
                freshness_reason="not_observed_in_bounded_retrieval",
            )
        ]
        more, next_position, upstream = False, position, state.get("upc")
        outcome = RetrievalOutcome.COMPLETE

        def append_record(kind: str, item: Any) -> None:
            collections: dict[str, list[Any]] = {
                "entity": facts,
                "relationship": relationships,
                "evidence": evidence,
                "unresolved": unresolved,
                "conflict": conflicts,
            }
            collections[kind].append(item)

        def resolve_record(selector: SubjectSelector) -> Any | None:
            if (
                selector.selector_type == "record_id"
                and selector.record_kind == "entity"
            ):
                assert selector.record_id is not None
                return canonical.get_entity(
                    scope.architecture_version_id, selector.record_id, scope.project_id
                )
            offset = 0
            while offset < p.canonical_max_rows_per_collection:
                batch, total = _list_collection_by_kind(
                    canonical,
                    selector.record_kind,
                    scope.architecture_version_id,
                    scope.project_id,
                    limit=min(
                        p.canonical_page_size,
                        p.canonical_max_rows_per_collection - offset,
                    ),
                    offset=offset,
                )
                for item in batch:
                    if (
                        selector.record_id and item.record_id == selector.record_id
                    ) or (
                        selector.logical_id and item.logical_id == selector.logical_id
                    ):
                        return item
                offset += len(batch)
                if not batch or offset >= total:
                    return None
            raise RetrievalCapacityExceededError(
                "Required canonical record is beyond scan policy"
            )

        if any(
            s and s.state in (ResolutionState.AMBIGUOUS, ResolutionState.INCOMPLETE)
            for s in subjects
        ):
            outcome = (
                RetrievalOutcome.AMBIGUOUS
                if any(s and s.state == ResolutionState.AMBIGUOUS for s in subjects)
                else RetrievalOutcome.PARTIAL
            )
        elif request.operation == RetrievalOperation.LOOKUP:
            if subject and subject.state == ResolutionState.RESOLVED:
                assert request.subject is not None and subject.selected_id is not None
                item = resolve_record(
                    SubjectSelector.from_record_id(
                        request.subject.record_kind, subject.selected_id
                    )
                )
                if item is None:
                    raise RetrievalIntegrityFailedError(
                        "Resolved canonical record disappeared"
                    )
                append_record(request.subject.record_kind, item)
            elif request.q is not None:
                if search is None:
                    raise RetrievalUnavailableError(
                        "Lexical search is unavailable", cause="search_unavailable"
                    )
                req = SearchRequest(
                    project_id=scope.project_id,
                    architecture_version_id=scope.architecture_version_id,
                    q=request.q,
                    document_kinds=tuple(
                        KnowledgeDocumentKind(k) for k in request.document_kinds
                    )
                    or None,
                    limit=request.limit,
                    cursor=upstream,
                    timeout_seconds=min(5.0, budget.call("search")),
                )
                page = search.search(req, actor_id=principal.actor_id)
                self._source_scope(page.scope, scope)
                budget.scanned("search_hits", len(page.items))
                state["search_request"] = req
                state["search_binding"] = (page.generation_id, page.index_uuid)
                more, upstream = page.has_more, page.next_cursor
                # One public paged pass per participating collection. Retain only
                # requested records, never a second full-model cache/index.
                wanted: dict[RecordKind, set[str]] = {}
                for hit in page.items:
                    self._source_scope(hit.scope, scope)
                    if hit.document_kind != KnowledgeDocumentKind.ARCHITECTURE_SUMMARY:
                        wanted.setdefault(
                            cast(RecordKind, hit.document_kind.value), set()
                        ).add(hit.canonical_reference)
                if sum(map(len, wanted.values())) > p.max_retained_candidates:
                    raise RetrievalCapacityExceededError(
                        "Retained candidate budget exceeded"
                    )
                matched: dict[tuple[str, str], Any] = {}
                for record_kind, keys in wanted.items():
                    offset = 0
                    exhausted = False
                    while offset < p.canonical_max_rows_per_collection:
                        batch, total = _list_collection_by_kind(
                            canonical,
                            record_kind,
                            scope.architecture_version_id,
                            scope.project_id,
                            limit=min(
                                p.canonical_page_size,
                                p.canonical_max_rows_per_collection - offset,
                            ),
                            offset=offset,
                        )
                        for item in batch:
                            if item.logical_id in keys:
                                identity = (record_kind, item.logical_id)
                                if identity in matched and matched[identity] != item:
                                    raise RetrievalIntegrityFailedError(
                                        "Conflicting canonical identity"
                                    )
                                matched[identity] = item
                        offset += len(batch)
                        if offset >= total or not batch:
                            exhausted = offset >= total
                            break
                    if not exhausted:
                        raise RetrievalCapacityExceededError(
                            "Required canonical search resolution exceeds scan policy"
                        )
                    if any((record_kind, key) not in matched for key in keys):
                        raise RetrievalIntegrityFailedError(
                            "Search reference missing canonically"
                        )
                for hit in page.items:
                    if hit.document_kind != KnowledgeDocumentKind.ARCHITECTURE_SUMMARY:
                        append_record(
                            hit.document_kind.value,
                            matched[(hit.document_kind.value, hit.canonical_reference)],
                        )
                observations.append(
                    SourceObservation(
                        source_kind=SourceKind.SEARCH,
                        contract_version=page.c1_version,
                        scope=scope,
                        search_scope=page.scope,
                        generation_id=page.generation_id,
                        index_uuid=page.index_uuid,
                        capabilities=tuple(
                            k
                            for k in ("lexical", "semantic", "hybrid")
                            if getattr(page.capabilities, k).value == "available"
                        ),
                        freshness=FreshnessState.UNKNOWN,
                        freshness_reason="not_observed_in_bounded_retrieval",
                    )
                )
            elif subject is None:
                raise RetrievalInvalidRequestError(
                    "Lookup requires a subject or literal query"
                )
        elif request.operation == RetrievalOperation.RELATIONSHIPS:
            if not subject or subject.state != ResolutionState.RESOLVED:
                raise RetrievalNotFoundError("Subject not found")
            batch, total = canonical.list_relationships(
                scope.architecture_version_id,
                scope.project_id,
                limit=request.limit,
                offset=position,
            )
            for rel in batch:
                outgoing = rel.source_logical_id == subject.selected_logical_id
                incoming = rel.target_logical_id == subject.selected_logical_id
                if (
                    (request.direction == TraversalDirection.OUTGOING and outgoing)
                    or (request.direction == TraversalDirection.INCOMING and incoming)
                    or (
                        request.direction == TraversalDirection.BOTH
                        and (outgoing or incoming)
                    )
                ):
                    if (
                        not request.relationship_kinds
                        or rel.kind in request.relationship_kinds
                    ):
                        relationships.append(rel)
            next_position = position + len(batch)
            more = next_position < total
        elif request.operation == RetrievalOperation.EVIDENCE:
            refs: set[str] | None = None
            selectors = (
                request.evidence_entity_ids,
                request.evidence_relationship_ids,
                request.evidence_ids,
            )
            if sum(bool(x) for x in selectors) > 1:
                raise RetrievalInvalidRequestError("Mixed evidence selector families")
            if sum(len(x) for x in selectors) > p.max_subjects:
                raise RetrievalCapacityExceededError(
                    "Evidence selector budget exceeded"
                )
            if request.evidence_entity_ids or request.evidence_relationship_ids:
                refs = set()
                evidence_record_kind: RecordKind = (
                    "entity" if request.evidence_entity_ids else "relationship"
                )
                for identifier in (
                    request.evidence_entity_ids or request.evidence_relationship_ids
                ):
                    item = resolve_record(
                        SubjectSelector.from_record_id(evidence_record_kind, identifier)
                    )
                    if item is None:
                        raise RetrievalNotFoundError()
                    refs.update(item.evidence_references)
            elif subject:
                if subject.state != ResolutionState.RESOLVED:
                    raise RetrievalNotFoundError()
                assert request.subject is not None and subject.selected_id is not None
                item = resolve_record(
                    SubjectSelector.from_record_id(
                        request.subject.record_kind, subject.selected_id
                    )
                )
                if item is None:
                    raise RetrievalIntegrityFailedError("Evidence subject disappeared")
                refs = (
                    set(item.evidence_references)
                    if hasattr(item, "evidence_references")
                    else {item.logical_id}
                )
            evidence_batch, total = canonical.list_evidence(
                scope.architecture_version_id,
                scope.project_id,
                limit=request.limit,
                offset=position,
            )
            evidence.extend(
                ev
                for ev in evidence_batch
                if (refs is None or ev.logical_id in refs)
                and (not request.evidence_ids or ev.record_id in request.evidence_ids)
            )
            next_position = position + len(evidence_batch)
            more = next_position < total
        else:
            if not subject or subject.state != ResolutionState.RESOLVED:
                raise RetrievalNotFoundError("Subject not found")
            if request.subject and request.subject.record_kind != "entity":
                raise RetrievalInvalidRequestError(
                    "Graph operations require entity subjects"
                )
            if graph is None:
                raise RetrievalUnavailableError(
                    "Graph retrieval is unavailable", cause="graph_unavailable"
                )
            common = dict(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
                timeout_seconds=min(5.0, budget.call("graph")),
            )
            if request.operation in (
                RetrievalOperation.DEPENDENCIES,
                RetrievalOperation.DEPENDENTS,
            ):
                kinds = (
                    tuple(GraphRelationshipKind(k) for k in request.relationship_kinds)
                    or APPROVED_DEPENDENCY_RELATIONSHIP_KINDS
                )
                if GraphRelationshipKind.CONTAINS in kinds:
                    raise RetrievalInvalidRequestError(
                        "Containment is separate from dependency traversal"
                    )
                cls = (
                    DependenciesRequest
                    if request.operation == RetrievalOperation.DEPENDENCIES
                    else DependentsRequest
                )
                req_graph = cls(
                    **common,
                    entity_id=subject.selected_id,
                    depth=request.graph_depth or 1,
                    node_limit=min(request.limit, p.max_graph_nodes),
                    edge_limit=min(p.max_graph_edges, p.max_selected_relationships),
                    relationship_kinds=kinds,
                    cursor=upstream,
                )
                result = (
                    graph.get_dependencies(req_graph)
                    if request.operation == RetrievalOperation.DEPENDENCIES
                    else graph.get_dependents(req_graph)
                )
            elif request.operation == RetrievalOperation.CONTAINMENT:
                result = graph.get_containment(
                    ContainmentRequest(
                        **common,
                        entity_id=subject.selected_id,
                        direction=P4ContainmentDirection(
                            request.containment_direction.value
                        ),
                        depth=request.graph_depth or 1,
                        node_limit=min(request.limit, p.max_graph_nodes),
                        edge_limit=min(p.max_graph_edges, p.max_selected_relationships),
                        cursor=upstream,
                    )
                )
            else:
                if not target or target.state != ResolutionState.RESOLVED:
                    raise RetrievalNotFoundError("Path target not found")
                result = graph.get_bounded_paths(
                    BoundedPathsRequest(
                        **common,
                        source_entity_id=subject.selected_id,
                        target_entity_id=target.selected_id,
                        max_depth=request.graph_depth or min(3, p.max_graph_depth),
                        path_limit=p.max_graph_paths,
                        relationship_kinds=tuple(
                            GraphRelationshipKind(k) for k in request.relationship_kinds
                        )
                        or None,
                    )
                )
            self._source_scope(result.scope, scope)
            if state.get("g_gen") and str(result.scope.generation_id) != str(
                state["g_gen"]
            ):
                raise RetrievalGenerationChangedError()
            state["g_gen"] = str(result.scope.generation_id)
            state["graph_binding"] = result.scope.generation_id
            if request.operation == RetrievalOperation.PATHS:
                nodes = [n for path in result.paths for n in path.nodes]
                edges = [e for path in result.paths for e in path.edges]
                more = False
                if result.truncated:
                    outcome = RetrievalOutcome.PARTIAL
            else:
                nodes, edges = result.nodes, result.edges
                upstream = result.next_cursor
                more = upstream is not None
                if result.truncated:
                    outcome = RetrievalOutcome.PARTIAL
            by_uuid = {}
            for node in nodes:
                fact = canonical.get_entity(
                    scope.architecture_version_id,
                    node.architecture_entity_id,
                    scope.project_id,
                )
                if fact is None or fact.logical_id != node.logical_id:
                    raise RetrievalIntegrityFailedError(
                        "Projected entity identity mismatch"
                    )
                by_uuid[fact.record_id] = fact
            facts.extend(by_uuid.values())
            for edge in edges:
                graph_rel = resolve_record(
                    SubjectSelector.from_record_id(
                        "relationship", edge.architecture_relationship_id
                    )
                )
                if (
                    graph_rel is None
                    or graph_rel.logical_id != edge.logical_id
                    or edge.source_entity_id not in by_uuid
                    or edge.target_entity_id not in by_uuid
                    or graph_rel.source_logical_id
                    != by_uuid[edge.source_entity_id].logical_id
                    or graph_rel.target_logical_id
                    != by_uuid[edge.target_entity_id].logical_id
                ):
                    raise RetrievalIntegrityFailedError(
                        "Projected relationship identity mismatch"
                    )
                relationships.append(graph_rel)
            if request.operation == RetrievalOperation.PATHS:
                paths = [
                    CanonicalPathView(
                        node_logical_ids=tuple(n.logical_id for n in path.nodes),
                        relationship_logical_ids=tuple(
                            e.logical_id for e in path.edges
                        ),
                        hop_count=path.hop_count,
                    )
                    for path in result.paths
                ]
            observations.append(
                SourceObservation(
                    source_kind=SourceKind.GRAPH,
                    contract_version="P4-Q1",
                    scope=scope,
                    generation_id=result.scope.generation_id,
                    graph_schema_version=result.scope.graph_schema_version,
                    projector_version=result.scope.projector_version,
                    freshness=FreshnessState.UNKNOWN,
                    freshness_reason="not_observed_in_bounded_retrieval",
                )
            )
        if more and not (facts or relationships or evidence or unresolved or conflicts):
            outcome = RetrievalOutcome.PARTIAL
        if outcome == RetrievalOutcome.COMPLETE and not (
            facts or relationships or evidence or unresolved or conflicts
        ):
            outcome = RetrievalOutcome.NO_EVIDENCE
        facts = list({f.logical_id: f for f in facts}.values())
        relationships = list({r.logical_id: r for r in relationships}.values())
        for count, maximum in (
            (len(facts), p.max_selected_facts),
            (len(relationships), p.max_selected_relationships),
            (len(evidence), p.max_selected_evidence),
            (len(unresolved), p.max_selected_unresolved),
            (len(conflicts), p.max_selected_conflicts),
        ):
            if count > maximum:
                raise RetrievalCapacityExceededError("Selected result budget exceeded")
        state.update(pos=next_position, upc=upstream, has_more=more)
        return KnowledgeQueryResponse(
            scope=scope,
            operation=request.operation,
            outcome=outcome,
            resolved_subject=subject,
            resolved_target=target,
            facts=tuple(facts),
            relationships=tuple(relationships),
            evidence=tuple(evidence),
            unresolved=tuple(unresolved),
            conflicts=tuple(conflicts),
            source_observations=tuple(observations),
            paths=tuple(paths),
            coverage=Coverage(
                considered_count=(
                    len(facts)
                    + len(relationships)
                    + len(evidence)
                    + len(unresolved)
                    + len(conflicts)
                ),
                selected_count=(
                    len(facts)
                    + len(relationships)
                    + len(evidence)
                    + len(unresolved)
                    + len(conflicts)
                ),
                scanned_count=sum(budget.rows.values()),
                count_known=not more,
                exhausted=not more and outcome != RetrievalOutcome.PARTIAL,
                truncated=more or outcome == RetrievalOutcome.PARTIAL,
            ),
        )

    def _finish(
        self,
        calls: _CanonicalCalls,
        scope: RetrievalScope,
        budget: RetrievalBudget,
        principal: RetrievalPrincipal,
        search: SearchReadAdapter | None,
        graph: GraphReadPort | None,
        state: dict[str, Any],
    ) -> None:
        calls.final = True
        if calls.get_version(scope.architecture_version_id, scope.project_id) != scope:
            raise RetrievalIntegrityFailedError(
                "Canonical header changed during retrieval"
            )
        if state.get("search_request"):
            if search is None:
                raise RetrievalUnavailableError()
            search.final_probe(
                state["search_request"],
                actor_id=principal.actor_id,
                remaining_budget=min(5.0, budget.call("search", final=True)),
            )
        if state.get("graph_binding"):
            if graph is None:
                raise RetrievalUnavailableError()
            if not graph.verify_generation_still_active(
                scope.project_id,
                scope.architecture_version_id,
                state["graph_binding"],
                timeout_seconds=min(5.0, budget.call("graph", final=True)),
            ):
                raise RetrievalGenerationChangedError()
        budget.remaining(reserve=False)

    def _ports(
        self,
        request: KnowledgeQueryRequest,
        budget: RetrievalBudget,
        state: dict[str, Any],
    ) -> tuple[SearchReadAdapter | None, GraphReadPort | None]:
        search = None
        graph = None
        if request.q is not None:
            port = self._search_port
            if port is None and self._search_factory:
                budget.call("search_setup")
                port = self._search_factory()
            if port is not None:
                search = SearchReadAdapter(
                    port,
                    bound_generation_id=(
                        UUID(state["s_gen"]) if state.get("s_gen") else None
                    ),
                    bound_index_uuid=state.get("s_idx"),
                )
        if request.operation in (
            RetrievalOperation.DEPENDENCIES,
            RetrievalOperation.DEPENDENTS,
            RetrievalOperation.CONTAINMENT,
            RetrievalOperation.PATHS,
        ):
            graph = self._graph_port
            if graph is None and self._graph_factory:
                budget.call("graph_setup")
                graph = self._graph_factory()
        return search, graph

    def query(
        self,
        request: KnowledgeQueryRequest,
        *,
        principal: RetrievalPrincipal,
        _budget: RetrievalBudget | None = None,
    ) -> KnowledgeQueryResponse:
        request = KnowledgeQueryRequest.model_validate(request)
        self._validate_request(request)
        if principal.project_id != request.project_id:
            raise RetrievalInvalidRequestError("Principal project mismatch")
        budget = _budget or RetrievalBudget(self._policy)
        budget.reserve_final_checks(
            search=request.q is not None,
            graph=request.operation
            in (
                RetrievalOperation.DEPENDENCIES,
                RetrievalOperation.DEPENDENTS,
                RetrievalOperation.CONTAINMENT,
                RetrievalOperation.PATHS,
            ),
        )
        state: dict[str, Any] = {}
        if request.cursor:
            state = decode_c3_cursor(
                request.cursor,
                secret_key=self._cursor_secret_key,
                principal=principal,
                scope=None,
                request=request,
                policy=self._policy,
            )
            if state["cp"] >= self._policy.max_chain_pages:
                raise RetrievalCapacityExceededError("Continuation chain exhausted")
            budget.work = state["cwu"]
        with operation_budget(budget):
            calls, scope = self._begin(
                request.architecture_version_id, request.project_id, principal, budget
            )
            for field in ("repository_id", "analysis_id", "snapshot_id"):
                expected = getattr(request, "expected_" + field)
                if expected and expected != getattr(scope, field):
                    raise RetrievalInvalidRequestError("Expected scope mismatch")
            if state and state["dig"] != scope.canonical_digest:
                raise RetrievalCursorInvalidError("Cursor canonical digest mismatch")
            search, graph = self._ports(request, budget, state)
            response = self._execute(
                request, principal, calls, scope, budget, search, graph, state
            )
            self._finish(calls, scope, budget, principal, search, graph, state)
            page = state.get("cp", 0) + 1
            next_cursor = None
            if (
                state.get("has_more")
                and page < self._policy.max_chain_pages
                and budget.work < self._policy.max_chain_work_units
            ):
                binding = state.get("search_binding")
                next_cursor = encode_c3_cursor(
                    secret_key=self._cursor_secret_key,
                    principal=principal,
                    scope=scope,
                    request=request,
                    policy=self._policy,
                    scan_position=state["pos"],
                    chain_page=page,
                    chain_work_units=budget.work,
                    search_generation_id=binding[0] if binding else None,
                    search_index_uuid=binding[1] if binding else None,
                    graph_generation_id=state.get("graph_binding"),
                    upstream_cursor=state.get("upc"),
                    ttl_seconds=self._policy.cursor_ttl_seconds,
                    issued_at=state.get("iat"),
                    expires_at=state.get("exp"),
                )
            response = KnowledgeQueryResponse.model_validate(
                response.model_copy(update={"next_cursor": next_cursor})
            )
            self._wire(response, budget)
            return response

    def read_evidence(
        self, request: EvidenceRequest, *, principal: RetrievalPrincipal
    ) -> EvidencePage:
        query = KnowledgeQueryRequest(
            project_id=request.project_id,
            architecture_version_id=request.architecture_version_id,
            operation=RetrievalOperation.EVIDENCE,
            evidence_entity_ids=request.entity_ids,
            evidence_relationship_ids=request.relationship_ids,
            evidence_ids=request.evidence_ids,
            limit=request.limit,
            cursor=request.cursor,
        )
        budget = RetrievalBudget(self._policy)
        result = self.query(query, principal=principal, _budget=budget)
        page = EvidencePage(
            scope=result.scope,
            items=result.evidence,
            total_items=(
                len(result.evidence)
                if result.coverage.exhausted and not request.cursor
                else None
            ),
            has_more=result.next_cursor is not None,
            next_cursor=result.next_cursor,
            coverage=result.coverage,
        )
        self._wire(page, budget)
        return page

    def _wire(self, model: BaseModel, budget: RetrievalBudget) -> None:
        payload = model.model_dump_json().encode()
        if len(payload) > self._policy.max_output_bytes:
            raise RetrievalCapacityExceededError("Response byte budget exceeded")
        budget.remaining(reserve=False)
        self.response_bytes = payload

    def build_context(
        self, request: ContextRequest, *, principal: RetrievalPrincipal
    ) -> ContextBundle:
        from backend.platform.knowledge.context import ContextBuilder
        from backend.platform.knowledge.evidence import EvidencePlanner

        request = ContextRequest.model_validate(request)
        if (
            len(request.subjects) > self._policy.max_subjects
            or len(request.operations) > self._policy.max_operations
        ):
            raise RetrievalCapacityExceededError(
                "Context plan exceeds operating policy"
            )
        budget = RetrievalBudget(self._policy)
        with operation_budget(budget):
            budget.reserve_final_checks(
                search=request.q is not None,
                graph=any(
                    op
                    in (
                        RetrievalOperation.DEPENDENCIES,
                        RetrievalOperation.DEPENDENTS,
                        RetrievalOperation.CONTAINMENT,
                        RetrievalOperation.PATHS,
                    )
                    for op in request.operations
                ),
            )
            calls, scope = self._begin(
                request.architecture_version_id, request.project_id, principal, budget
            )
            results = []
            omissions = []
            state: dict[str, Any] = {}
            search = None
            graph = None
            selectors = list(request.subjects)
            if request.q is not None:
                lexical = KnowledgeQueryRequest(
                    project_id=scope.project_id,
                    architecture_version_id=scope.architecture_version_id,
                    operation=RetrievalOperation.LOOKUP,
                    q=request.q,
                    limit=self._policy.canonical_page_size,
                )
                search, _ = self._ports(lexical, budget, state)
                try:
                    found = self._execute(
                        lexical, principal, calls, scope, budget, search, None, state
                    )
                except RetrievalUnavailableError:
                    if (
                        SourceKind.SEARCH not in request.optional_sources
                        or SourceKind.SEARCH in request.required_sources
                    ):
                        raise
                    state.clear()
                    omissions.append(
                        OmissionSummary(
                            source=SourceKind.SEARCH,
                            reason="optional_source_unavailable",
                            omitted_count=0,
                        )
                    )
                else:
                    results.append(found)
                    selectors.extend(
                        SubjectSelector.from_record_id("entity", f.record_id)
                        for f in found.facts
                    )
                    if state.get("has_more"):
                        omissions.append(
                            OmissionSummary(
                                source=SourceKind.SEARCH,
                                reason="scan_incomplete",
                                omitted_count=0,
                            )
                        )
                    state.pop("upc", None)
                    state.pop("pos", None)
                    state.pop("has_more", None)
            if len(selectors) > self._policy.max_subjects:
                raise RetrievalCapacityExceededError("Selected subject budget exceeded")
            for selector in selectors:
                for op in dict.fromkeys(
                    (RetrievalOperation.LOOKUP, *request.operations)
                ):
                    if op == RetrievalOperation.EVIDENCE:
                        continue
                    req = KnowledgeQueryRequest(
                        project_id=scope.project_id,
                        architecture_version_id=scope.architecture_version_id,
                        operation=op,
                        subject=selector,
                        target=request.target,
                        limit=self._policy.canonical_page_size,
                    )
                    candidate_search, candidate_graph = self._ports(req, budget, {})
                    search = search or candidate_search
                    graph = graph or candidate_graph
                    try:
                        result = self._execute(
                            req, principal, calls, scope, budget, search, graph, state
                        )
                    except RetrievalUnavailableError:
                        source = (
                            SourceKind.GRAPH
                            if op
                            in (
                                RetrievalOperation.DEPENDENCIES,
                                RetrievalOperation.DEPENDENTS,
                                RetrievalOperation.CONTAINMENT,
                                RetrievalOperation.PATHS,
                            )
                            else SourceKind.SEARCH
                        )
                        if (
                            source not in request.optional_sources
                            or source in request.required_sources
                        ):
                            raise
                        omissions.append(
                            OmissionSummary(
                                source=source,
                                reason="optional_source_unavailable",
                                omitted_count=0,
                            )
                        )
                        continue
                    results.append(result)
                    if (
                        op == RetrievalOperation.LOOKUP
                        and result.resolved_subject
                        and result.resolved_subject.state != ResolutionState.RESOLVED
                    ):
                        break
                    if state.get("has_more"):
                        omissions.append(
                            OmissionSummary(
                                source=SourceKind.CANONICAL,
                                reason="scan_incomplete",
                                omitted_count=0,
                            )
                        )
                    state.pop("pos", None)
                    state.pop("upc", None)
                    state.pop("has_more", None)
            participating = {SourceKind.CANONICAL} | {
                o.source_kind for r in results for o in r.source_observations
            }
            if set(request.required_sources) - participating:
                raise RetrievalUnavailableError(
                    "Required context source did not participate"
                )
            facts = [f for r in results for f in r.facts]
            rels = [r for result in results for r in result.relationships]
            planned = EvidencePlanner(
                cast(CanonicalReadPort, calls), self._policy
            ).plan_evidence(
                version_id=scope.architecture_version_id,
                project_id=scope.project_id,
                facts=facts,
                relationships=rels,
                include_evidence=request.include_evidence,
                include_conflicts=request.include_conflicts,
                include_unresolved=request.include_unresolved,
            )
            omissions.extend(planned.omissions)
            if planned.conflict_coverage_incomplete:
                omissions.append(
                    OmissionSummary(
                        source=SourceKind.CANONICAL,
                        reason="conflict_scan_incomplete",
                        omitted_count=0,
                    )
                )
            plan = RetrievalPlan(
                request_fingerprint=hashlib.sha256(
                    request.model_dump_json().encode()
                ).hexdigest(),
                operations=request.operations,
                subjects=request.subjects,
                target=request.target,
                required_sources=request.required_sources,
                optional_sources=request.optional_sources,
                policy_fingerprint=self._policy.compute_fingerprint(),
            )
            bundle = ContextBuilder(
                scope=scope, plan=plan, policy=self._policy
            ).build_bundle(
                source_observations=tuple(
                    o for r in results for o in r.source_observations
                ),
                resolved_subjects=tuple(
                    r.resolved_subject for r in results if r.resolved_subject
                ),
                facts=facts,
                relationships=rels,
                evidence=planned.evidence,
                conflicts=planned.conflicts,
                unresolved=planned.unresolved,
                omissions=omissions,
                rationales=tuple(
                    SelectionRationale(
                        code=(
                            SelectionRationaleCode.LEXICAL_CANDIDATE
                            if any(
                                o.source_kind == SourceKind.SEARCH
                                for o in r.source_observations
                            )
                            else (
                                SelectionRationaleCode.GRAPH_CONTEXT
                                if r.operation
                                not in (
                                    RetrievalOperation.LOOKUP,
                                    RetrievalOperation.RELATIONSHIPS,
                                )
                                else (
                                    SelectionRationaleCode.EXACT_NAME
                                    if r.resolved_subject
                                    and r.resolved_subject.selector.selector_type
                                    == "entity_name"
                                    else SelectionRationaleCode.EXPLICIT_IDENTITY
                                )
                            )
                        ),
                        target_logical_id=f.logical_id,
                        target_kind=f.kind,
                        originating_operation=r.operation,
                    )
                    for r in results
                    for f in r.facts
                )
                + tuple(
                    SelectionRationale(
                        code=SelectionRationaleCode.DIRECT_RELATIONSHIP,
                        target_logical_id=r.logical_id,
                        target_kind=r.kind,
                        originating_operation=RetrievalOperation.RELATIONSHIPS,
                    )
                    for r in rels
                )
                + tuple(
                    SelectionRationale(
                        code=(
                            SelectionRationaleCode.CONFLICTING_EVIDENCE
                            if ev.polarity == "conflicting"
                            else SelectionRationaleCode.SUPPORTING_EVIDENCE
                        ),
                        target_logical_id=ev.logical_id,
                        target_kind="evidence",
                    )
                    for ev in planned.evidence
                ),
            )
            self._finish(calls, scope, budget, principal, search, graph, state)
            self._wire(bundle, budget)
            return bundle
