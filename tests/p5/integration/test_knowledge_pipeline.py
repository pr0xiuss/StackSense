"""Mocked consumer-composition tests, not physical-service acceptance.

Verifies end-to-end integration across canonical, search, and graph source adapters,
query service, evidence planner, context builder, and FastAPI endpoints.
Adheres to §7A.6, §7A.10, §7A.12, and §7A.13 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.api.v1.retrieval import router as retrieval_router
from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_delegated_context,
)
from backend.platform.analysis.architecture.dto import (
    ArchitectureCollectionResponse,
    ArchitectureConflictResponse,
    ArchitectureEntityResponse,
    ArchitectureEvidenceResponse,
    ArchitectureRelationshipResponse,
    ArchitectureUnresolvedResponse,
    ArchitectureVersionResponse,
)
from backend.platform.errors import ArchitectureResultNotFoundError
from backend.platform.graph.model import ProjectionCounts
from backend.platform.graph.query_contracts import (
    GraphNode,
    GraphSubgraph,
)
from backend.platform.knowledge.contracts import (
    SearchCapabilities,
    SearchHit,
    SearchPage,
    SearchRequest,
)
from backend.platform.knowledge.evidence import EvidencePlanner
from backend.platform.knowledge.retrieval import KnowledgeQueryService
from backend.platform.knowledge.retrieval_adapters import (
    CanonicalReadAdapter,
    GraphReadAdapter,
    SearchReadAdapter,
)
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    KnowledgeQueryRequest,
    RetrievalOperation,
    RetrievalPrincipal,
)
from backend.platform.knowledge.retrieval_dependencies import (
    get_canonical_read_port,
    get_evidence_planner,
    get_graph_read_port,
    get_knowledge_query_service,
    get_retrieval_cursor_secret,
    get_retrieval_policy,
    get_search_read_port,
)
from tests.p5.knowledge.conftest import make_test_scope


class MockArchitectureQueryService:
    """Mock of ArchitectureQueryService providing canonical responses."""

    def __init__(self, version_id: UUID, project_id: UUID) -> None:
        self.version_id = version_id
        self.project_id = project_id
        self.analysis_id = uuid4()
        self.repository_id = uuid4()
        self.snapshot_id = uuid4()
        self.published_at = datetime.now(UTC)
        self.entities: list[ArchitectureEntityResponse] = []
        self.relationships: list[ArchitectureRelationshipResponse] = []
        self.evidence: list[ArchitectureEvidenceResponse] = []
        self.unresolved: list[ArchitectureUnresolvedResponse] = []
        self.conflicts: list[ArchitectureConflictResponse] = []

    def get_version(
        self, version_id: UUID, project_id: UUID
    ) -> ArchitectureVersionResponse:
        if version_id != self.version_id or project_id != self.project_id:
            raise ArchitectureResultNotFoundError(
                details={"version_id": str(version_id)}
            )
        return ArchitectureVersionResponse(
            id=version_id,
            analysis_id=self.analysis_id,
            project_id=project_id,
            repository_id=self.repository_id,
            snapshot_id=self.snapshot_id,
            sequence_number=1,
            architecture_schema_version="1.0.0",
            ir_schema_version="1.0.0",
            content_digest="c" * 64,
            entity_count=len(self.entities),
            relationship_count=len(self.relationships),
            evidence_count=len(self.evidence),
            unresolved_relationship_count=len(self.unresolved),
            conflict_count=len(self.conflicts),
            completeness={},
            published_at=self.published_at,
        )

    def get_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> ArchitectureEntityResponse:
        for e in self.entities:
            if e.id == entity_id:
                return e
        raise ArchitectureResultNotFoundError(details={"entity_id": str(entity_id)})

    def list_entities(
        self, version_id: UUID, project_id: UUID, **kwargs: Any
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.entities, total=len(self.entities), limit=100, offset=0
        )

    def list_relationships(
        self, version_id: UUID, project_id: UUID, **kwargs: Any
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.relationships,
            total=len(self.relationships),
            limit=100,
            offset=0,
        )

    def list_evidence(
        self, version_id: UUID, project_id: UUID, **kwargs: Any
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.evidence, total=len(self.evidence), limit=100, offset=0
        )

    def list_unresolved(
        self, version_id: UUID, project_id: UUID, **kwargs: Any
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.unresolved, total=len(self.unresolved), limit=100, offset=0
        )

    def list_conflicts(
        self, version_id: UUID, project_id: UUID, **kwargs: Any
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.conflicts, total=len(self.conflicts), limit=100, offset=0
        )


class MockSearchReader:
    """Mock SearchReader adhering to SearchReadPort protocol."""

    def __init__(self, scope: Any, generation_id: UUID, index_uuid: str) -> None:
        self.scope = scope
        self.generation_id = generation_id
        self.index_uuid = index_uuid
        self.hits: list[SearchHit] = []

    def search(self, request: SearchRequest, *, actor_id: UUID) -> SearchPage:
        return SearchPage(
            c1_version="1.0.0",
            scope=self.scope,
            generation_id=self.generation_id,
            index_uuid=self.index_uuid,
            items=tuple(self.hits),
            total_hits=len(self.hits),
            has_more=False,
            capabilities=SearchCapabilities(),
        )


class MockGraphGenerationReader:
    """Mock GraphGenerationReader for graph adapter tests."""

    def __init__(self, scope: Any, generation_id: UUID) -> None:
        self.scope = scope
        self.generation_id = generation_id

    def get_active_generation(
        self, project_id: UUID, architecture_version_id: UUID
    ) -> Any:
        return type(
            "GraphGen",
            (),
            {
                "generation_id": self.generation_id,
                "scope": self.scope,
                "counts": ProjectionCounts(
                    total_nodes=2,
                    total_edges=1,
                    entity_nodes=2,
                    relationship_edges=1,
                    unresolved_edges=0,
                ),
            },
        )()


class MockGraphQueryService:
    """Mock GraphQueryService for graph queries."""

    def __init__(self, generation_id: UUID) -> None:
        self.generation_id = generation_id

    def get_neighbors(
        self,
        scope: Any,
        node_id: UUID,
        direction: str,
        *,
        edge_types: Any = None,
        limit: int = 25,
        cursor: Any = None,
    ) -> GraphSubgraph:
        return GraphSubgraph(
            c1_version="1.0.0",
            scope=scope,
            generation_id=self.generation_id,
            nodes=(
                GraphNode(
                    node_id=node_id,
                    logical_id="architecture://entity/service/web",
                    kind="service",
                    name="WebService",
                    namespace=("app", "web"),
                    static_status="confirmed",
                    evidence_count=1,
                ),
            ),
            edges=(),
            has_more=False,
            total_matches=1,
        )


@pytest.fixture
def pipeline_fixture():
    project_id = uuid4()
    version_id = uuid4()
    c0_scope = make_test_scope(
        project_id=project_id, architecture_version_id=version_id
    )

    # 1. Canonical query service & adapter
    arch_svc = MockArchitectureQueryService(version_id, project_id)
    canonical_port = CanonicalReadAdapter(arch_svc)

    entity1_id = uuid4()
    entity2_id = uuid4()
    rel1_id = uuid4()

    arch_svc.entities.extend(
        [
            ArchitectureEntityResponse(
                id=entity1_id,
                logical_id="architecture://entity/service/auth",
                kind="service",
                name="AuthService",
                namespace=("app", "auth"),
                status="confirmed",
                evidence_ids=("ev-auth-1",),
                source_ir_keys=("ir:auth",),
                metadata={"framework": "fastapi"},
            ),
            ArchitectureEntityResponse(
                id=entity2_id,
                logical_id="architecture://entity/database/postgres",
                kind="database",
                name="AuthDatabase",
                namespace=("app", "auth"),
                status="confirmed",
                evidence_ids=("ev-db-1",),
                source_ir_keys=("ir:db",),
                metadata={"database_engine": "postgresql"},
            ),
        ]
    )

    arch_svc.relationships.append(
        ArchitectureRelationshipResponse(
            id=rel1_id,
            logical_id="architecture://rel/calls/auth-to-db",
            kind="calls",
            status="confirmed",
            source_logical_id="architecture://entity/service/auth",
            target_logical_id="architecture://entity/database/postgres",
            evidence_ids=("ev-auth-1",),
            source_ir_keys=("ir:rel:1",),
            metadata={},
        )
    )

    arch_svc.evidence.extend(
        [
            ArchitectureEvidenceResponse(
                id=uuid4(),
                logical_id="ev-auth-1",
                source_record_type="entity",
                path="src/auth/service.py",
                artifact_id=uuid4(),
                source_fact_key="fact-auth",
                producer_id="p3.analyzer",
                producer_version="1.0.0",
                strength="direct_source",
                polarity="supporting",
                source_range={"start_line": 1, "end_line": 20},
                metadata={},
            ),
            ArchitectureEvidenceResponse(
                id=uuid4(),
                logical_id="ev-db-1",
                source_record_type="entity",
                path="src/auth/db.py",
                artifact_id=uuid4(),
                source_fact_key="fact-db",
                producer_id="p3.analyzer",
                producer_version="1.0.0",
                strength="direct_source",
                polarity="supporting",
                source_range={"start_line": 1, "end_line": 15},
                metadata={},
            ),
        ]
    )

    arch_svc.conflicts.append(
        ArchitectureConflictResponse(
            id=uuid4(),
            logical_id="architecture://conflict/auth-db-pool",
            conflict_type="pool_size_mismatch",
            subject_key="architecture://entity/service/auth",
            evidence_ids=("ev-auth-1",),
            details={"configured_max": 20, "detected_max": 10},
        )
    )

    arch_svc.unresolved.append(
        ArchitectureUnresolvedResponse(
            id=uuid4(),
            logical_id="architecture://unresolved/external-sso",
            kind="calls",
            source_logical_id="architecture://entity/service/auth",
            target_descriptor="https://sso.corporate.com/oauth",
            reason="ambiguous_external_target",
            status="unresolved",
            evidence_ids=("ev-auth-1",),
            candidate_references=(),
            metadata={},
        )
    )

    # 2. Search reader & adapter
    search_gen_id = uuid4()
    search_idx_uuid = "pipeline-search-idx-uuid"
    search_reader = MockSearchReader(c0_scope, search_gen_id, search_idx_uuid)
    search_port = SearchReadAdapter(search_reader)

    # 3. Graph services & adapter
    graph_gen_id = uuid4()
    graph_gen_reader = MockGraphGenerationReader(c0_scope, graph_gen_id)
    graph_query_svc = MockGraphQueryService(graph_gen_id)
    graph_port = GraphReadAdapter(graph_gen_reader, graph_query_svc)

    # 4. M3 policy, query service & evidence planner
    policy = RetrievalPolicy(canonical_page_size=25)
    cursor_secret = "pipeline-secret-key-at-least-32-chars-long"

    query_svc = KnowledgeQueryService(
        canonical_port=canonical_port,
        search_port=search_port,
        graph_port=graph_port,
        policy=policy,
        cursor_secret_key=cursor_secret,
    )

    evidence_planner = EvidencePlanner(
        canonical_port=canonical_port,
        policy=policy,
    )

    # 5. FastAPI App
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(retrieval_router, prefix="/api/v1")

    actor_id = uuid4()
    context = DelegatedRequestContext(
        actor_id=actor_id,
        role="OWNER",
        is_service=True,
        project_id=project_id,
        correlation_id="corr-pipeline-test",
    )

    app.dependency_overrides[get_delegated_context] = lambda: context
    app.dependency_overrides[get_canonical_read_port] = lambda: canonical_port
    app.dependency_overrides[get_search_read_port] = lambda: search_port
    app.dependency_overrides[get_graph_read_port] = lambda: graph_port
    app.dependency_overrides[get_retrieval_policy] = lambda: policy
    app.dependency_overrides[get_retrieval_cursor_secret] = lambda: cursor_secret
    app.dependency_overrides[get_knowledge_query_service] = lambda: query_svc
    app.dependency_overrides[get_evidence_planner] = lambda: evidence_planner

    client = TestClient(app)
    return (
        client,
        app,
        query_svc,
        evidence_planner,
        canonical_port,
        search_reader,
        graph_query_svc,
        c0_scope,
        project_id,
        version_id,
    )


def test_end_to_end_query_pipeline(pipeline_fixture):
    """End-to-end lookup and relationships operations through HTTP routes."""
    client, _, _, _, _, _, _, _, project_id, version_id = pipeline_fixture

    url = (
        f"/api/v1/architecture-versions/{version_id}/knowledge/query"
        f"?project_id={project_id}"
    )

    # 1. Lookup
    lookup_body = {
        "project_id": str(project_id),
        "architecture_version_id": str(version_id),
        "operation": "lookup",
        "subject": {
            "selector_type": "logical_id",
            "logical_id": "architecture://entity/service/auth",
        },
    }
    resp = client.post(url, json=lookup_body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["c3_version"] == "1.0.0"
    assert data["resolved_subject"]["selected_logical_id"] == (
        "architecture://entity/service/auth"
    )
    assert len(data["facts"]) == 1
    assert data["facts"][0]["name"] == "AuthService"

    # 2. Relationships
    rel_body = {
        "project_id": str(project_id),
        "architecture_version_id": str(version_id),
        "operation": "relationships",
        "subject": {
            "selector_type": "logical_id",
            "logical_id": "architecture://entity/service/auth",
        },
    }
    resp = client.post(url, json=rel_body)
    assert resp.status_code == 200, resp.text
    rel_data = resp.json()
    assert len(rel_data["relationships"]) == 1
    assert rel_data["relationships"][0]["kind"] == "calls"


def test_end_to_end_context_assembly_pipeline(pipeline_fixture):
    """End-to-end ContextBundle assembly across canonical facts, evidence,
    and conflicts.
    """
    client, _, _, _, _, _, _, _, project_id, version_id = pipeline_fixture

    url = (
        f"/api/v1/architecture-versions/{version_id}/knowledge/context"
        f"?project_id={project_id}"
    )
    body = {
        "project_id": str(project_id),
        "architecture_version_id": str(version_id),
        "subjects": [
            {
                "selector_type": "logical_id",
                "logical_id": "architecture://entity/service/auth",
            }
        ],
        "operations": ["lookup", "relationships"],
        "include_evidence": True,
        "include_conflicts": True,
        "include_unresolved": True,
    }

    resp = client.post(url, json=body)
    assert resp.status_code == 200, resp.text
    bundle = resp.json()

    assert bundle["c3_version"] == "1.0.0"
    assert len(bundle["semantic_digest"]) == 64
    assert len(bundle["facts"]) >= 1
    assert len(bundle["relationships"]) >= 1
    assert len(bundle["evidence"]) >= 1
    assert len(bundle["unresolved"]) >= 1
    assert len(bundle["conflicts"]) >= 1
    assert bundle["outcome"] == "complete"
    assert len(bundle["rationales"]) >= 2


def test_graceful_degradation_when_search_and_graph_unconfigured(pipeline_fixture):
    """Pipeline operates cleanly with canonical data when search and graph are None."""
    (
        client,
        app,
        _,
        evidence_planner,
        canonical_port,
        _,
        _,
        _,
        project_id,
        version_id,
    ) = pipeline_fixture

    policy = RetrievalPolicy()
    secret = "degraded-secret-key-at-least-32-chars-long"

    # Instantiate query service without search and graph ports
    degraded_query_svc = KnowledgeQueryService(
        canonical_port=canonical_port,
        search_port=None,
        graph_port=None,
        policy=policy,
        cursor_secret_key=secret,
    )

    app.dependency_overrides[get_search_read_port] = lambda: None
    app.dependency_overrides[get_graph_read_port] = lambda: None
    app.dependency_overrides[get_knowledge_query_service] = lambda: degraded_query_svc

    # 1. Query endpoint still succeeds
    url_query = (
        f"/api/v1/architecture-versions/{version_id}/knowledge/query"
        f"?project_id={project_id}"
    )
    resp = client.post(
        url_query,
        json={
            "project_id": str(project_id),
            "architecture_version_id": str(version_id),
            "operation": "lookup",
            "subject": {
                "selector_type": "logical_id",
                "logical_id": "architecture://entity/service/auth",
            },
        },
    )
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "complete"

    # 2. Context assembly endpoint still succeeds
    url_ctx = (
        f"/api/v1/architecture-versions/{version_id}/knowledge/context"
        f"?project_id={project_id}"
    )
    resp_ctx = client.post(
        url_ctx,
        json={
            "project_id": str(project_id),
            "architecture_version_id": str(version_id),
            "subjects": [
                {
                    "selector_type": "logical_id",
                    "logical_id": "architecture://entity/service/auth",
                }
            ],
            "operations": ["lookup"],
        },
    )
    assert resp_ctx.status_code == 200
    bundle = resp_ctx.json()
    assert bundle["outcome"] == "complete"
    assert len(bundle["semantic_digest"]) == 64


def test_canonical_only_ignores_unrelated_search_generation_change(pipeline_fixture):
    """Unrelated search state must not affect a canonical-only request."""
    (
        client,
        app,
        _,
        _,
        canonical_port,
        search_reader,
        graph_query_svc,
        c0_scope,
        project_id,
        version_id,
    ) = pipeline_fixture

    # Change search generation to simulate concurrent rebuild
    search_reader.generation_id = uuid4()

    url = (
        f"/api/v1/architecture-versions/{version_id}/knowledge/query"
        f"?project_id={project_id}"
    )
    resp = client.post(
        url,
        json={
            "project_id": str(project_id),
            "architecture_version_id": str(version_id),
            "operation": "lookup",
            "subject": {
                "selector_type": "logical_id",
                "logical_id": "architecture://entity/service/auth",
            },
        },
    )
    # Canonical-only retrieval does not depend on or probe search.
    assert resp.status_code == 200


def test_canonical_only_never_calls_optional_ports(pipeline_fixture):
    """Consumer fakes prove optional ports are unused, not physical isolation."""
    (
        _,
        _,
        query_svc,
        evidence_planner,
        _,
        _,
        _,
        _,
        project_id,
        version_id,
    ) = pipeline_fixture

    # These are consumer fakes, not transaction proofs (see real-services tests).
    search = pipeline_fixture[5]
    graph = pipeline_fixture[6]
    search.search = MagicMock(side_effect=AssertionError("Unexpected search"))
    graph.get_dependencies = MagicMock(side_effect=AssertionError("Unexpected graph"))

    principal = RetrievalPrincipal(
        actor_id=uuid4(),
        project_id=project_id,
        role="OWNER",
    )

    req = KnowledgeQueryRequest(
        project_id=project_id,
        architecture_version_id=version_id,
        operation=RetrievalOperation.LOOKUP,
        subject={
            "selector_type": "logical_id",
            "logical_id": "architecture://entity/service/auth",
        },
    )

    resp = query_svc.query(req, principal=principal)
    assert resp.outcome.value == "complete"

    # Actual PG read-only enforcement is covered by the real-service tests.
    search.search.assert_not_called()
    graph.get_dependencies.assert_not_called()
