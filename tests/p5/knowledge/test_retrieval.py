"""Unit tests for P5-C3 retrieval planner, subject resolution, and query operations.

Adheres to §7A.4, §7A.5, §7A.6, and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from backend.platform.graph.query_contracts import (
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphPathResult,
    GraphReadScope,
    GraphSubgraph,
)
from backend.platform.knowledge.contracts import (
    SearchCapabilities,
    SearchHit,
    SearchPage,
    SearchRequest,
)
from backend.platform.knowledge.retrieval import (
    KnowledgeQueryService,
    decode_c3_cursor,
    encode_c3_cursor,
    resolve_subject,
)
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalFactView,
    CanonicalReadPort,
    EvidenceItemView,
    KnowledgeQueryRequest,
    RelationshipView,
    ResolutionState,
    RetrievalCapacityExceededError,
    RetrievalCursorExpiredError,
    RetrievalCursorInvalidError,
    RetrievalInvalidRequestError,
    RetrievalNotFoundError,
    RetrievalOperation,
    RetrievalOutcome,
    RetrievalPrincipal,
    RetrievalScope,
    SubjectSelector,
    TraversalDirection,
)


class MockCanonicalPort(CanonicalReadPort):
    def __init__(self, scope: RetrievalScope) -> None:
        self.scope = scope
        self.entities: list[CanonicalFactView] = []
        self.relationships: list[RelationshipView] = []
        self.evidence: list[EvidenceItemView] = []

    def get_version(self, version_id: UUID, project_id: UUID) -> RetrievalScope:
        if (
            version_id != self.scope.architecture_version_id
            or project_id != self.scope.project_id
        ):
            raise RetrievalNotFoundError("Version not found")
        return self.scope

    def get_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> CanonicalFactView | None:
        for e in self.entities:
            if e.record_id == entity_id:
                return e
        return None

    def list_entities(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int, **kwargs
    ):
        paged = self.entities[offset : offset + limit]
        return tuple(paged), len(self.entities)

    def list_relationships(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int, **kwargs
    ):
        paged = self.relationships[offset : offset + limit]
        return tuple(paged), len(self.relationships)

    def list_evidence(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int, **kwargs
    ):
        paged = self.evidence[offset : offset + limit]
        return tuple(paged), len(self.evidence)

    def list_unresolved(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ):
        return (), 0

    def list_conflicts(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ):
        return (), 0


class MockSearchPort:
    def __init__(self, gen_id: UUID, idx_uuid: str) -> None:
        self.gen_id = gen_id
        self.idx_uuid = idx_uuid
        self.hits: list[SearchHit] = []

    def search(self, request: SearchRequest, *, actor_id: UUID) -> SearchPage:
        from tests.p5.knowledge.conftest import make_test_scope

        scope = make_test_scope(
            project_id=request.project_id,
            architecture_version_id=request.architecture_version_id,
        )
        return SearchPage(
            scope=scope,
            generation_id=self.gen_id,
            index_uuid=self.idx_uuid,
            hits=tuple(self.hits),
            total_hits=len(self.hits),
            capabilities=SearchCapabilities(),
        )


class MockGraphPort:
    def __init__(self, gen_id: UUID) -> None:
        self.gen_id = gen_id
        self.nodes: list[GraphNode] = []
        self.edges: list[GraphEdge] = []
        self.active = True

    def resolve_active_generation(
        self, project_id: UUID, architecture_version_id: UUID, *, timeout_seconds: float
    ):
        return GraphReadScope(
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            generation_id=self.gen_id,
            generation_key="gen-k1",
            graph_schema_version="1.0.0",
            projector_version="1.0.0",
            total_nodes=len(self.nodes),
            total_edges=len(self.edges),
        )

    def verify_generation_still_active(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        *,
        timeout_seconds: float,
    ) -> bool:
        return self.active and generation_id == self.gen_id

    def get_dependencies(self, request):
        return self._subgraph(request.project_id, request.architecture_version_id)

    def get_dependents(self, request):
        return self._subgraph(request.project_id, request.architecture_version_id)

    def get_containment(self, request):
        return self._subgraph(request.project_id, request.architecture_version_id)

    def get_bounded_paths(self, request):
        scope = self.resolve_active_generation(
            request.project_id, request.architecture_version_id, timeout_seconds=1.0
        )
        path = GraphPath(
            nodes=tuple(self.nodes),
            edges=tuple(self.edges),
            weight=1.0,
            hop_count=len(self.edges),
        )
        return GraphPathResult(
            scope=scope,
            paths=(path,) if self.nodes else (),
            total_paths=1 if self.nodes else 0,
            truncated=False,
        )

    def _subgraph(self, project_id: UUID, version_id: UUID):
        scope = self.resolve_active_generation(
            project_id, version_id, timeout_seconds=1.0
        )
        return GraphSubgraph(
            scope=scope,
            nodes=tuple(self.nodes),
            edges=tuple(self.edges),
            total_manifest_nodes=len(self.nodes),
            total_manifest_edges=len(self.edges),
            loaded_nodes=len(self.nodes),
            loaded_edges=len(self.edges),
            truncated=False,
        )


def _setup_test_environment():
    prj = uuid4()
    ver = uuid4()
    scope = RetrievalScope(
        project_id=prj,
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=ver,
        sequence_number=1,
        canonical_digest="c" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        published_at=datetime.now(UTC),
    )
    principal = RetrievalPrincipal(actor_id=uuid4(), project_id=prj, role="member")
    policy = RetrievalPolicy()
    secret_key = "test-retrieval-cursor-secret-key-32b"
    return prj, ver, scope, principal, policy, secret_key


def test_resolve_subject_record_id():
    prj, ver, scope, _, policy, _ = _setup_test_environment()
    canonical = MockCanonicalPort(scope)
    ent_id = uuid4()
    fact = CanonicalFactView(
        record_id=ent_id,
        logical_id="entity://auth",
        kind="service",
        name="AuthService",
        status="CONFIRMED",
    )
    canonical.entities.append(fact)

    # 1. Found entity by UUID
    res = resolve_subject(
        SubjectSelector.from_record_id("entity", ent_id),
        canonical,
        ver,
        prj,
        max_scan_rows=100,
    )
    assert res.state == ResolutionState.RESOLVED
    assert res.selected_id == ent_id
    assert res.selected_logical_id == "entity://auth"

    # 2. Not found entity by UUID
    res_nf = resolve_subject(
        SubjectSelector.from_record_id("entity", uuid4()),
        canonical,
        ver,
        prj,
        max_scan_rows=100,
    )
    assert res_nf.state == ResolutionState.NOT_FOUND


def test_resolve_subject_name_and_namespace():
    prj, ver, scope, _, policy, _ = _setup_test_environment()
    canonical = MockCanonicalPort(scope)
    ent1 = CanonicalFactView(
        record_id=uuid4(),
        logical_id="entity://core/auth",
        kind="service",
        name="AuthService",
        namespace=("core", "auth"),
        status="CONFIRMED",
    )
    ent2 = CanonicalFactView(
        record_id=uuid4(),
        logical_id="entity://ext/auth",
        kind="service",
        name="AuthService",
        namespace=("ext", "auth"),
        status="CONFIRMED",
    )
    canonical.entities.extend([ent1, ent2])

    # 1. Ambiguous without namespace
    res_amb = resolve_subject(
        SubjectSelector.from_entity_name("AuthService"),
        canonical,
        ver,
        prj,
        max_scan_rows=100,
    )
    assert res_amb.state == ResolutionState.AMBIGUOUS
    assert len(res_amb.candidates) == 2

    # 2. Unique match with explicit namespace
    res_uniq = resolve_subject(
        SubjectSelector.from_entity_name("AuthService", namespace=("core", "auth")),
        canonical,
        ver,
        prj,
        max_scan_rows=100,
    )
    assert res_uniq.state == ResolutionState.RESOLVED
    assert res_uniq.selected_id == ent1.record_id
    assert res_uniq.selected_logical_id == ent1.logical_id


def test_knowledge_query_service_project_scope_enforcement():
    prj, ver, scope, principal, policy, secret_key = _setup_test_environment()
    canonical = MockCanonicalPort(scope)
    svc = KnowledgeQueryService(canonical, policy=policy, cursor_secret_key=secret_key)

    foreign_req = KnowledgeQueryRequest(
        project_id=uuid4(),  # Mismatched project
        architecture_version_id=ver,
        operation=RetrievalOperation.LOOKUP,
    )
    with pytest.raises(RetrievalInvalidRequestError):
        svc.query(foreign_req, principal=principal)


def test_knowledge_query_service_lookup_operation():
    prj, ver, scope, principal, policy, secret_key = _setup_test_environment()
    canonical = MockCanonicalPort(scope)
    ent_id = uuid4()
    fact = CanonicalFactView(
        record_id=ent_id,
        logical_id="entity://db",
        kind="database",
        name="Postgres",
        status="CONFIRMED",
    )
    canonical.entities.append(fact)

    svc = KnowledgeQueryService(canonical, policy=policy, cursor_secret_key=secret_key)
    req = KnowledgeQueryRequest(
        project_id=prj,
        architecture_version_id=ver,
        operation=RetrievalOperation.LOOKUP,
        subject=SubjectSelector.from_record_id("entity", ent_id),
    )
    resp = svc.query(req, principal=principal)
    assert resp.outcome == RetrievalOutcome.COMPLETE
    assert len(resp.facts) == 1
    assert resp.facts[0].record_id == ent_id
    assert resp.resolved_subject is not None
    assert resp.resolved_subject.state == ResolutionState.RESOLVED


def test_knowledge_query_service_relationships_operation():
    prj, ver, scope, principal, policy, secret_key = _setup_test_environment()
    canonical = MockCanonicalPort(scope)
    ent_id = uuid4()
    fact = CanonicalFactView(
        record_id=ent_id,
        logical_id="entity://service-a",
        kind="service",
        name="ServiceA",
        status="CONFIRMED",
    )
    canonical.entities.append(fact)

    rel_out = RelationshipView(
        record_id=uuid4(),
        logical_id="rel://calls-b",
        kind="calls",
        status="CONFIRMED",
        source_logical_id="entity://service-a",
        target_logical_id="entity://service-b",
    )
    rel_in = RelationshipView(
        record_id=uuid4(),
        logical_id="rel://called-by-c",
        kind="calls",
        status="CONFIRMED",
        source_logical_id="entity://service-c",
        target_logical_id="entity://service-a",
    )
    canonical.relationships.extend([rel_out, rel_in])

    svc = KnowledgeQueryService(canonical, policy=policy, cursor_secret_key=secret_key)

    # 1. Outgoing direction
    req_out = KnowledgeQueryRequest(
        project_id=prj,
        architecture_version_id=ver,
        operation=RetrievalOperation.RELATIONSHIPS,
        subject=SubjectSelector.from_record_id("entity", ent_id),
        direction=TraversalDirection.OUTGOING,
    )
    resp_out = svc.query(req_out, principal=principal)
    assert len(resp_out.relationships) == 1
    assert resp_out.relationships[0].logical_id == "rel://calls-b"

    # 2. Both directions
    req_both = KnowledgeQueryRequest(
        project_id=prj,
        architecture_version_id=ver,
        operation=RetrievalOperation.RELATIONSHIPS,
        subject=SubjectSelector.from_record_id("entity", ent_id),
        direction=TraversalDirection.BOTH,
    )
    resp_both = svc.query(req_both, principal=principal)
    assert len(resp_both.relationships) == 2


def test_c3_stateless_cursor_signing_and_validation():
    prj, ver, scope, principal, policy, secret_key = _setup_test_environment()
    req = KnowledgeQueryRequest(
        project_id=prj,
        architecture_version_id=ver,
        operation=RetrievalOperation.LOOKUP,
        q="Service",
    )

    # Encode cursor
    cursor = encode_c3_cursor(
        secret_key=secret_key,
        principal=principal,
        scope=scope,
        request=req,
        policy=policy,
        scan_position=25,
        chain_page=1,
        chain_work_units=25,
        ttl_seconds=300.0,
    )
    assert isinstance(cursor, str)

    # Decode cursor
    decoded = decode_c3_cursor(
        cursor,
        secret_key=secret_key,
        principal=principal,
        scope=scope,
        request=req,
        policy=policy,
    )
    assert decoded["pos"] == 25
    assert decoded["cp"] == 1
    assert decoded["act"] == str(principal.actor_id)

    # Forged actor fails
    foreign_principal = RetrievalPrincipal(
        actor_id=uuid4(), project_id=prj, role="member"
    )
    with pytest.raises(RetrievalCursorInvalidError):
        decode_c3_cursor(
            cursor,
            secret_key=secret_key,
            principal=foreign_principal,
            scope=scope,
            request=req,
            policy=policy,
        )

    # Tampered signature fails
    tampered = cursor[:-4] + "AAAA"
    with pytest.raises(RetrievalCursorInvalidError):
        decode_c3_cursor(
            tampered,
            secret_key=secret_key,
            principal=principal,
            scope=scope,
            request=req,
            policy=policy,
        )


def test_c3_stateless_cursor_expiration():
    prj, ver, scope, principal, policy, secret_key = _setup_test_environment()
    req = KnowledgeQueryRequest(
        project_id=prj,
        architecture_version_id=ver,
        operation=RetrievalOperation.LOOKUP,
    )
    # Cursor with negative TTL (already expired)
    expired_cursor = encode_c3_cursor(
        secret_key=secret_key,
        principal=principal,
        scope=scope,
        request=req,
        policy=policy,
        scan_position=10,
        chain_page=1,
        chain_work_units=10,
        ttl_seconds=300.0,
        issued_at=1000.0,
        expires_at=1300.0,
    )
    with pytest.raises(RetrievalCursorExpiredError):
        decode_c3_cursor(
            expired_cursor,
            secret_key=secret_key,
            principal=principal,
            scope=scope,
            request=req,
            policy=policy,
        )


def test_c3_stateless_cursor_chain_page_limit():
    prj, ver, scope, principal, policy, secret_key = _setup_test_environment()
    req = KnowledgeQueryRequest(
        project_id=prj,
        architecture_version_id=ver,
        operation=RetrievalOperation.LOOKUP,
    )
    # Cursor with chain page exceeding policy max_chain_pages
    exceeded_cursor = encode_c3_cursor(
        secret_key=secret_key,
        principal=principal,
        scope=scope,
        request=req,
        policy=policy,
        scan_position=10,
        chain_page=policy.max_chain_pages + 1,
        chain_work_units=10,
        ttl_seconds=300.0,
    )
    with pytest.raises(RetrievalCapacityExceededError):
        decode_c3_cursor(
            exceeded_cursor,
            secret_key=secret_key,
            principal=principal,
            scope=scope,
            request=req,
            policy=policy,
        )
