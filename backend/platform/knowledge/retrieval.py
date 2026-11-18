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
from typing import Any
from uuid import UUID

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
    GraphReadAdapter,
    SearchReadAdapter,
)
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    C3_CONTRACT_VERSION,
    CanonicalFactView,
    CanonicalReadPort,
    ConflictView,
    ContainmentDirection,
    Coverage,
    EvidenceItemView,
    FreshnessState,
    GraphReadPort,
    KnowledgeQueryPort,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    RelationshipView,
    ResolutionState,
    ResolvedSubject,
    RetrievalCapacityExceededError,
    RetrievalCursorExpiredError,
    RetrievalCursorInvalidError,
    RetrievalDeadlineExceededError,
    RetrievalGenerationChangedError,
    RetrievalInvalidRequestError,
    RetrievalOperation,
    RetrievalOutcome,
    RetrievalPrincipal,
    RetrievalScope,
    RetrievalUnavailableError,
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
    """Compute deterministic fingerprint of the query request."""
    data: dict[str, Any] = {
        "project_id": str(request.project_id),
        "architecture_version_id": str(request.architecture_version_id),
        "operation": request.operation.value,
        "direction": request.direction.value,
        "containment_direction": request.containment_direction.value,
        "q": request.q,
        "relationship_kinds": list(request.relationship_kinds),
        "document_kinds": list(request.document_kinds),
        "graph_depth": request.graph_depth,
        "limit": request.limit,
    }
    if request.subject:
        data["subject"] = {
            "type": request.subject.selector_type,
            "kind": request.subject.record_kind,
            "id": str(request.subject.record_id) if request.subject.record_id else None,
            "logical_id": request.subject.logical_id,
            "name": request.subject.name,
            "namespace": (
                list(request.subject.namespace) if request.subject.namespace else None
            ),
        }
    if request.target:
        data["target"] = {
            "type": request.target.selector_type,
            "kind": request.target.record_kind,
            "id": str(request.target.record_id) if request.target.record_id else None,
            "logical_id": request.target.logical_id,
            "name": request.target.name,
            "namespace": (
                list(request.target.namespace) if request.target.namespace else None
            ),
        }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
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
        "iat": now,
        "exp": now + ttl_seconds,
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
    scope: RetrievalScope,
    request: KnowledgeQueryRequest,
    policy: RetrievalPolicy,
) -> dict[str, Any]:
    """Validate and decode stateless HMAC-signed C3 cursor (§7A.6)."""
    if len(cursor) > policy.max_cursor_bytes:
        raise RetrievalCursorInvalidError(
            "Cursor length exceeds maximum allowed byte budget"
        )

    try:
        raw_env = base64.urlsafe_b64decode(cursor.encode("ascii"))
        envelope = json.loads(raw_env)
        data_bytes = base64.urlsafe_b64decode(envelope["d"].encode("ascii"))
        provided_sig = base64.urlsafe_b64decode(envelope["s"].encode("ascii"))
    except Exception as exc:
        raise RetrievalCursorInvalidError(
            "Malformed cursor encoding or envelope", cause=str(exc)
        ) from exc

    expected_sig = hmac.new(
        secret_key.encode("utf-8"), data_bytes, hashlib.sha256
    ).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise RetrievalCursorInvalidError("Cursor HMAC signature verification failed")

    try:
        payload = json.loads(data_bytes)
    except Exception as exc:
        raise RetrievalCursorInvalidError(
            "Malformed cursor JSON payload", cause=str(exc)
        ) from exc

    # Enforce exact version and parameter binding
    if payload.get("v") != _TOKEN_VERSION:
        raise RetrievalCursorInvalidError("Unsupported cursor token version")
    if payload.get("act") != str(principal.actor_id):
        raise RetrievalCursorInvalidError("Cursor actor binding mismatch")
    if payload.get("prj") != str(scope.project_id):
        raise RetrievalCursorInvalidError("Cursor project binding mismatch")
    if payload.get("ver") != str(scope.architecture_version_id):
        raise RetrievalCursorInvalidError(
            "Cursor architecture version binding mismatch"
        )
    if payload.get("dig") != scope.canonical_digest:
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
        limit = min(100, max_scan_rows)
        scanned = 0
        while scanned < max_scan_rows:
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
        limit = min(100, max_scan_rows)
        scanned = 0
        matched: list[SubjectCandidate] = []
        while scanned < max_scan_rows:
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
        limit = min(100, max_scan_rows)
        scanned = 0
        matched_named: list[SubjectCandidate] = []
        total = 0
        while scanned < max_scan_rows:
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


class KnowledgeQueryService(KnowledgeQueryPort):
    """Application service orchestrating controlled C3 retrieval operations."""

    def __init__(
        self,
        canonical_port: CanonicalReadPort,
        *,
        search_port: SearchReadPort | None = None,
        graph_port: GraphReadPort | None = None,
        policy: RetrievalPolicy,
        cursor_secret_key: str,
    ) -> None:
        self._canonical_port = canonical_port
        self._search_port = search_port
        self._graph_port = graph_port
        self._policy = policy
        self._cursor_secret_key = cursor_secret_key

    def query(
        self,
        request: KnowledgeQueryRequest,
        *,
        principal: RetrievalPrincipal,
    ) -> KnowledgeQueryResponse:
        start_time = time.monotonic()
        deadline = start_time + self._policy.total_deadline_seconds

        # 1. Authorization check
        if principal.project_id != request.project_id:
            raise RetrievalInvalidRequestError(
                f"Principal project_id ({principal.project_id}) does not match "
                f"request ({request.project_id})"
            )

        # 2. Scope verification
        scope = self._canonical_port.get_version(
            request.architecture_version_id, request.project_id
        )
        if (
            request.expected_repository_id
            and scope.repository_id != request.expected_repository_id
        ):
            raise RetrievalInvalidRequestError(
                "Repository ID mismatch against canonical published header"
            )
        if (
            request.expected_analysis_id
            and scope.analysis_id != request.expected_analysis_id
        ):
            raise RetrievalInvalidRequestError(
                "Analysis ID mismatch against canonical published header"
            )
        if (
            request.expected_snapshot_id
            and scope.snapshot_id != request.expected_snapshot_id
        ):
            raise RetrievalInvalidRequestError(
                "Snapshot ID mismatch against canonical published header"
            )

        # 3. Cursor handling & initial position
        scan_position = 0
        chain_page = 1
        chain_work_units = 0
        bound_search_gen: UUID | None = None
        bound_search_idx: str | None = None
        bound_graph_gen: UUID | None = None
        upstream_cursor: str | None = None

        if request.cursor:
            cursor_data = decode_c3_cursor(
                request.cursor,
                secret_key=self._cursor_secret_key,
                principal=principal,
                scope=scope,
                request=request,
                policy=self._policy,
            )
            scan_position = int(cursor_data.get("pos", 0))
            chain_page = int(cursor_data.get("cp", 1)) + 1
            chain_work_units = int(cursor_data.get("cwu", 0))
            if cursor_data.get("s_gen"):
                bound_search_gen = UUID(cursor_data["s_gen"])
            bound_search_idx = cursor_data.get("s_idx")
            if cursor_data.get("g_gen"):
                bound_graph_gen = UUID(cursor_data["g_gen"])
            upstream_cursor = cursor_data.get("upc")

        # Create source adapters with bound generation states
        search_adapter: SearchReadAdapter | None = None
        if self._search_port is not None:
            search_adapter = SearchReadAdapter(
                self._search_port,
                bound_generation_id=bound_search_gen,
                bound_index_uuid=bound_search_idx,
            )

        graph_adapter: GraphReadAdapter | None = None
        if self._graph_port is not None:
            if isinstance(self._graph_port, GraphReadAdapter):
                graph_adapter = self._graph_port
                if bound_graph_gen and graph_adapter._generation_id is None:
                    graph_adapter._generation_id = bound_graph_gen

        source_observations: list[SourceObservation] = []
        canonical_obs = SourceObservation(
            source_kind=SourceKind.CANONICAL,
            contract_version=C3_CONTRACT_VERSION,
            scope=scope,
            capabilities=("read_entity", "list_relationships", "list_evidence"),
            freshness=FreshnessState.UNKNOWN,
            freshness_reason="not_observed_in_bounded_retrieval",
            advisory_only=True,
        )
        source_observations.append(canonical_obs)

        # 4. Resolve Subject (and Target if applicable)
        resolved_subject: ResolvedSubject | None = None
        resolved_target: ResolvedSubject | None = None

        if request.subject:
            resolved_subject = resolve_subject(
                request.subject,
                self._canonical_port,
                request.architecture_version_id,
                request.project_id,
                max_scan_rows=self._policy.canonical_max_rows_per_collection,
            )

        if request.target:
            resolved_target = resolve_subject(
                request.target,
                self._canonical_port,
                request.architecture_version_id,
                request.project_id,
                max_scan_rows=self._policy.canonical_max_rows_per_collection,
            )

        # If subject was ambiguous or not found and required, return early outcome
        if resolved_subject and resolved_subject.state == ResolutionState.AMBIGUOUS:
            return KnowledgeQueryResponse(
                scope=scope,
                operation=request.operation,
                outcome=RetrievalOutcome.AMBIGUOUS,
                resolved_subject=resolved_subject,
                resolved_target=resolved_target,
                coverage=Coverage(
                    considered_count=len(resolved_subject.candidates),
                    selected_count=0,
                    scanned_count=len(resolved_subject.candidates),
                    count_known=True,
                    exhausted=resolved_subject.scan_complete,
                ),
                source_observations=tuple(source_observations),
            )

        # 5. Dispatch Operation
        facts: list[CanonicalFactView] = []
        relationships: list[RelationshipView] = []
        evidence: list[EvidenceItemView] = []
        unresolved: list[UnresolvedView] = []
        conflicts: list[ConflictView] = []
        has_more = False
        next_pos = scan_position
        used_search = False
        used_graph = False

        if request.operation == RetrievalOperation.LOOKUP:
            if resolved_subject and resolved_subject.state == ResolutionState.RESOLVED:
                assert resolved_subject.selected_id is not None
                if resolved_subject.selector.record_kind == "entity":
                    fact = self._canonical_port.get_entity(
                        request.architecture_version_id,
                        resolved_subject.selected_id,
                        request.project_id,
                    )
                    if fact:
                        facts.append(fact)
            elif request.q:
                # Search-assisted candidate discovery if search port is available
                if search_adapter is not None:
                    used_search = True
                    search_req = SearchRequest(
                        project_id=request.project_id,
                        architecture_version_id=request.architecture_version_id,
                        q=request.q,
                        document_kinds=(KnowledgeDocumentKind.ENTITY,),
                        limit=request.limit,
                        cursor=upstream_cursor,
                    )
                    spage = search_adapter.search(
                        search_req, actor_id=principal.actor_id
                    )
                    upstream_cursor = spage.next_cursor
                    has_more = bool(spage.has_more)

                    # Rehydrate hits canonically via logical_id
                    for hit in spage.items:
                        res = resolve_subject(
                            SubjectSelector.from_logical_id(
                                "entity", hit.canonical_reference
                            ),
                            self._canonical_port,
                            request.architecture_version_id,
                            request.project_id,
                            max_scan_rows=self._policy.canonical_max_rows_per_collection,
                        )
                        if res.state == ResolutionState.RESOLVED and res.selected_id:
                            f = self._canonical_port.get_entity(
                                request.architecture_version_id,
                                res.selected_id,
                                request.project_id,
                            )
                            if f:
                                facts.append(f)

                    source_observations.append(
                        SourceObservation(
                            source_kind=SourceKind.SEARCH,
                            contract_version=spage.c1_version,
                            scope=scope,
                            generation_id=spage.generation_id,
                            index_uuid=spage.index_uuid,
                            capabilities=tuple(
                                cap
                                for cap in ("lexical", "semantic", "hybrid")
                                if getattr(spage.capabilities, cap).value == "AVAILABLE"
                            ),
                            freshness=FreshnessState.UNKNOWN,
                            freshness_reason="not_observed_in_bounded_retrieval",
                        )
                    )
                else:
                    # Fallback to bounded canonical scan
                    paged_facts, total = self._canonical_port.list_entities(
                        request.architecture_version_id,
                        request.project_id,
                        limit=request.limit,
                        offset=scan_position,
                    )
                    facts.extend(paged_facts)
                    next_pos = scan_position + len(paged_facts)
                    has_more = next_pos < total

        elif request.operation == RetrievalOperation.RELATIONSHIPS:
            if (
                not resolved_subject
                or resolved_subject.state != ResolutionState.RESOLVED
            ):
                raise RetrievalInvalidRequestError(
                    "Resolved entity subject required for relationships operation"
                )

            paged_rels, total = self._canonical_port.list_relationships(
                request.architecture_version_id,
                request.project_id,
                limit=request.limit,
                offset=scan_position,
            )
            subj_lid = resolved_subject.selected_logical_id

            # Filter incident relationships for subject in original direction
            for rel in paged_rels:
                is_outgoing = rel.source_logical_id == subj_lid
                is_incoming = rel.target_logical_id == subj_lid

                match_dir = (
                    (request.direction == TraversalDirection.OUTGOING and is_outgoing)
                    or (
                        request.direction == TraversalDirection.INCOMING and is_incoming
                    )
                    or (
                        request.direction == TraversalDirection.BOTH
                        and (is_outgoing or is_incoming)
                    )
                )
                if not match_dir:
                    continue

                if (
                    request.relationship_kinds
                    and rel.kind not in request.relationship_kinds
                ):
                    continue

                relationships.append(rel)

            next_pos = scan_position + len(paged_rels)
            has_more = next_pos < total

        elif request.operation in (
            RetrievalOperation.DEPENDENCIES,
            RetrievalOperation.DEPENDENTS,
        ):
            if (
                not resolved_subject
                or resolved_subject.state != ResolutionState.RESOLVED
            ):
                raise RetrievalInvalidRequestError(
                    f"Resolved entity subject required for {request.operation.value}"
                )
            if self._graph_port is None:
                raise RetrievalUnavailableError(
                    "Graph query port is unavailable for graph dependency queries"
                )

            used_graph = True
            rem_timeout = max(
                0.1,
                deadline - time.monotonic() - self._policy.finalization_reserve_seconds,
            )
            assert resolved_subject.selected_id is not None

            if request.operation == RetrievalOperation.DEPENDENCIES:
                req_dep = DependenciesRequest(
                    project_id=request.project_id,
                    architecture_version_id=request.architecture_version_id,
                    entity_id=resolved_subject.selected_id,
                    depth=request.graph_depth or 1,
                    node_limit=min(request.limit, self._policy.max_graph_nodes),
                    edge_limit=self._policy.max_graph_edges,
                    relationship_kinds=(
                        tuple(
                            GraphRelationshipKind(k) for k in request.relationship_kinds
                        )
                        if request.relationship_kinds
                        else APPROVED_DEPENDENCY_RELATIONSHIP_KINDS
                    ),
                    timeout_seconds=rem_timeout,
                    cursor=upstream_cursor,
                )
                subgraph = self._graph_port.get_dependencies(req_dep)
            else:
                req_dependents = DependentsRequest(
                    project_id=request.project_id,
                    architecture_version_id=request.architecture_version_id,
                    entity_id=resolved_subject.selected_id,
                    depth=request.graph_depth or 1,
                    node_limit=min(request.limit, self._policy.max_graph_nodes),
                    edge_limit=self._policy.max_graph_edges,
                    relationship_kinds=(
                        tuple(
                            GraphRelationshipKind(k) for k in request.relationship_kinds
                        )
                        if request.relationship_kinds
                        else APPROVED_DEPENDENCY_RELATIONSHIP_KINDS
                    ),
                    timeout_seconds=rem_timeout,
                    cursor=upstream_cursor,
                )
                subgraph = self._graph_port.get_dependents(req_dependents)

            upstream_cursor = subgraph.next_cursor
            has_more = bool(subgraph.truncated)

            # Rehydrate nodes and edges canonically
            for gnode in subgraph.nodes:
                facts.append(
                    CanonicalFactView(
                        record_id=gnode.architecture_entity_id,
                        logical_id=gnode.logical_id,
                        kind=gnode.canonical_kind,
                        name=gnode.name,
                        namespace=(gnode.namespace,) if gnode.namespace else None,
                        status=gnode.fact_status,
                        metadata=dict(gnode.metadata),
                        evidence_count=len(gnode.evidence_logical_ids),
                        evidence_references=tuple(gnode.evidence_logical_ids),
                    )
                )

            for gedge in subgraph.edges:
                relationships.append(
                    RelationshipView(
                        record_id=gedge.architecture_relationship_id,
                        logical_id=gedge.logical_id,
                        kind=gedge.canonical_kind,
                        status=gedge.status,
                        source_id=gedge.source_entity_id,
                        target_id=gedge.target_entity_id,
                        source_logical_id=str(gedge.source_entity_id),
                        target_logical_id=str(gedge.target_entity_id),
                        evidence_references=tuple(gedge.evidence_logical_ids),
                    )
                )

            source_observations.append(
                SourceObservation(
                    source_kind=SourceKind.GRAPH,
                    contract_version=C3_CONTRACT_VERSION,
                    scope=scope,
                    generation_id=subgraph.scope.generation_id,
                    graph_schema_version=subgraph.scope.graph_schema_version,
                    projector_version=subgraph.scope.projector_version,
                    capabilities=("dependencies", "dependents"),
                    freshness=FreshnessState.UNKNOWN,
                    freshness_reason="not_observed_in_bounded_retrieval",
                )
            )

        elif request.operation == RetrievalOperation.CONTAINMENT:
            if (
                not resolved_subject
                or resolved_subject.state != ResolutionState.RESOLVED
            ):
                raise RetrievalInvalidRequestError(
                    "Resolved entity subject required for containment operation"
                )
            if self._graph_port is None:
                raise RetrievalUnavailableError(
                    "Graph query port is unavailable for containment queries"
                )

            used_graph = True
            rem_timeout = max(
                0.1,
                deadline - time.monotonic() - self._policy.finalization_reserve_seconds,
            )
            assert resolved_subject.selected_id is not None

            p4_dir = (
                P4ContainmentDirection.PARENTS
                if request.containment_direction == ContainmentDirection.PARENTS
                else (
                    P4ContainmentDirection.CHILDREN
                    if request.containment_direction == ContainmentDirection.CHILDREN
                    else P4ContainmentDirection.BOTH
                )
            )

            req_cont = ContainmentRequest(
                project_id=request.project_id,
                architecture_version_id=request.architecture_version_id,
                entity_id=resolved_subject.selected_id,
                direction=p4_dir,
                depth=request.graph_depth or 1,
                node_limit=min(request.limit, self._policy.max_graph_nodes),
                edge_limit=self._policy.max_graph_edges,
                timeout_seconds=rem_timeout,
                cursor=upstream_cursor,
            )
            subgraph = self._graph_port.get_containment(req_cont)
            upstream_cursor = subgraph.next_cursor
            has_more = bool(subgraph.truncated)

            for gnode in subgraph.nodes:
                facts.append(
                    CanonicalFactView(
                        record_id=gnode.architecture_entity_id,
                        logical_id=gnode.logical_id,
                        kind=gnode.canonical_kind,
                        name=gnode.name,
                        namespace=(gnode.namespace,) if gnode.namespace else None,
                        status=gnode.fact_status,
                        metadata=dict(gnode.metadata),
                        evidence_count=len(gnode.evidence_logical_ids),
                        evidence_references=tuple(gnode.evidence_logical_ids),
                    )
                )
            for gedge in subgraph.edges:
                relationships.append(
                    RelationshipView(
                        record_id=gedge.architecture_relationship_id,
                        logical_id=gedge.logical_id,
                        kind=gedge.canonical_kind,
                        status=gedge.status,
                        source_id=gedge.source_entity_id,
                        target_id=gedge.target_entity_id,
                        source_logical_id=str(gedge.source_entity_id),
                        target_logical_id=str(gedge.target_entity_id),
                        evidence_references=tuple(gedge.evidence_logical_ids),
                    )
                )

            source_observations.append(
                SourceObservation(
                    source_kind=SourceKind.GRAPH,
                    contract_version=C3_CONTRACT_VERSION,
                    scope=scope,
                    generation_id=subgraph.scope.generation_id,
                    graph_schema_version=subgraph.scope.graph_schema_version,
                    projector_version=subgraph.scope.projector_version,
                    capabilities=("containment",),
                    freshness=FreshnessState.UNKNOWN,
                    freshness_reason="not_observed_in_bounded_retrieval",
                )
            )

        elif request.operation == RetrievalOperation.PATHS:
            if (
                not resolved_subject
                or resolved_subject.state != ResolutionState.RESOLVED
            ):
                raise RetrievalInvalidRequestError(
                    "Resolved entity subject required for paths operation"
                )
            if not resolved_target or resolved_target.state != ResolutionState.RESOLVED:
                raise RetrievalInvalidRequestError(
                    "Resolved entity target required for paths operation"
                )
            if self._graph_port is None:
                raise RetrievalUnavailableError(
                    "Graph query port is unavailable for paths query"
                )

            used_graph = True
            rem_timeout = max(
                0.1,
                deadline - time.monotonic() - self._policy.finalization_reserve_seconds,
            )
            assert resolved_subject.selected_id is not None
            assert resolved_target.selected_id is not None

            req_paths = BoundedPathsRequest(
                project_id=request.project_id,
                architecture_version_id=request.architecture_version_id,
                source_entity_id=resolved_subject.selected_id,
                target_entity_id=resolved_target.selected_id,
                max_depth=request.graph_depth or 3,
                path_limit=min(self._policy.max_graph_paths, 25),
                timeout_seconds=rem_timeout,
            )
            path_res = self._graph_port.get_bounded_paths(req_paths)
            has_more = False  # Paths operations are non-paginated per §7A.6

            for path in path_res.paths:
                for node in path.nodes:
                    facts.append(
                        CanonicalFactView(
                            record_id=node.architecture_entity_id,
                            logical_id=node.logical_id,
                            kind=node.canonical_kind,
                            name=node.name,
                            namespace=(node.namespace,) if node.namespace else None,
                            status=node.fact_status,
                            metadata=dict(node.metadata),
                            evidence_count=len(node.evidence_logical_ids),
                            evidence_references=tuple(node.evidence_logical_ids),
                        )
                    )
                for edge in path.edges:
                    relationships.append(
                        RelationshipView(
                            record_id=edge.architecture_relationship_id,
                            logical_id=edge.logical_id,
                            kind=edge.canonical_kind,
                            status=edge.status,
                            source_id=edge.source_entity_id,
                            target_id=edge.target_entity_id,
                            source_logical_id=str(edge.source_entity_id),
                            target_logical_id=str(edge.target_entity_id),
                            evidence_references=tuple(edge.evidence_logical_ids),
                        )
                    )

            source_observations.append(
                SourceObservation(
                    source_kind=SourceKind.GRAPH,
                    contract_version=C3_CONTRACT_VERSION,
                    scope=scope,
                    generation_id=path_res.scope.generation_id,
                    graph_schema_version=path_res.scope.graph_schema_version,
                    projector_version=path_res.scope.projector_version,
                    capabilities=("paths",),
                    freshness=FreshnessState.UNKNOWN,
                    freshness_reason="not_observed_in_bounded_retrieval",
                )
            )

        elif request.operation == RetrievalOperation.EVIDENCE:
            entity_id = resolved_subject.selected_id if resolved_subject else None
            paged_ev, total = self._canonical_port.list_evidence(
                request.architecture_version_id,
                request.project_id,
                limit=request.limit,
                offset=scan_position,
                entity_id=entity_id,
            )
            evidence.extend(paged_ev)
            next_pos = scan_position + len(paged_ev)
            has_more = next_pos < total

        # 6. Conditional Final Checks (§7A.6)
        rem_budget = deadline - time.monotonic()
        if rem_budget <= 0:
            raise RetrievalDeadlineExceededError(
                "Retrieval operation exceeded total deadline before final checks"
            )

        if used_search and search_adapter is not None:
            # Perform single final search validation probe (§7A.6)
            search_adapter.final_probe(
                SearchRequest(
                    project_id=request.project_id,
                    architecture_version_id=request.architecture_version_id,
                    q=request.q or "*",
                    document_kinds=(KnowledgeDocumentKind.ENTITY,),
                    limit=1,
                ),
                actor_id=principal.actor_id,
                remaining_budget=rem_budget,
            )

        if (
            used_graph
            and graph_adapter is not None
            and graph_adapter.bound_generation_id is not None
        ):
            active = graph_adapter.verify_generation_still_active(
                request.project_id,
                request.architecture_version_id,
                graph_adapter.bound_generation_id,
                timeout_seconds=rem_budget,
            )
            if not active:
                raise RetrievalGenerationChangedError(
                    "Graph generation is no longer active at final check"
                )

        # 7. Next cursor generation if continuation exists
        next_cursor: str | None = None
        if has_more and chain_page < self._policy.max_chain_pages:
            s_gen = search_adapter.bound_generation_id if search_adapter else None
            s_idx = search_adapter.bound_index_uuid if search_adapter else None
            g_gen = graph_adapter.bound_generation_id if graph_adapter else None
            next_cursor = encode_c3_cursor(
                secret_key=self._cursor_secret_key,
                principal=principal,
                scope=scope,
                request=request,
                policy=self._policy,
                scan_position=next_pos,
                chain_page=chain_page,
                chain_work_units=chain_work_units
                + len(facts)
                + len(relationships)
                + len(evidence),
                search_generation_id=s_gen,
                search_index_uuid=s_idx,
                graph_generation_id=g_gen,
                upstream_cursor=upstream_cursor,
                ttl_seconds=self._policy.cursor_ttl_seconds,
            )

        outcome = RetrievalOutcome.COMPLETE
        if (
            not facts
            and not relationships
            and not evidence
            and not unresolved
            and not conflicts
        ):
            outcome = RetrievalOutcome.NO_EVIDENCE

        total_selected = (
            len(facts)
            + len(relationships)
            + len(evidence)
            + len(unresolved)
            + len(conflicts)
        )
        coverage = Coverage(
            considered_count=total_selected,
            selected_count=total_selected,
            scanned_count=total_selected,
            count_known=True,
            exhausted=not has_more,
            truncated=has_more,
        )

        return KnowledgeQueryResponse(
            scope=scope,
            operation=request.operation,
            outcome=outcome,
            resolved_subject=resolved_subject,
            resolved_target=resolved_target,
            facts=tuple(facts),
            relationships=tuple(relationships),
            evidence=tuple(evidence),
            unresolved=tuple(unresolved),
            conflicts=tuple(conflicts),
            source_observations=tuple(source_observations),
            coverage=coverage,
            next_cursor=next_cursor,
        )


__all__ = [
    "KnowledgeQueryService",
    "decode_c3_cursor",
    "encode_c3_cursor",
    "resolve_subject",
]
