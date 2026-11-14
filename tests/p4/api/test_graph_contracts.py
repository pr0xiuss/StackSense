"""P4-D1 Graph API contract serialization, parameter mapping, and OpenAPI tests."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.api.app import app
from backend.platform.config import get_settings
from backend.platform.graph.api_contracts import (
    P4_D1_CONTRACT_VERSION,
    GraphErrorResponse,
    ProjectionAttemptSummary,
    ProjectionRebuildAcceptedResponse,
    ProjectionStatusResponse,
)
from backend.platform.graph.api_dependencies import get_graph_api_service
from backend.platform.graph.api_service import (
    SqlAlchemyGraphProjectionStatusReader,
)
from backend.platform.graph.dependencies import get_graph_query_service
from backend.platform.graph.model import (
    PROJECTION_TYPE,
    ProjectionAttemptState,
    ProjectionCounts,
    ProjectionPublicState,
)
from backend.platform.graph.persistence import (
    Base,
    GraphProjectionAttemptModel,
    GraphProjectionResourceModel,
)
from backend.platform.graph.query_contracts import (
    DEFAULT_QUERY_EDGES,
    DEFAULT_QUERY_NODES,
    DEFAULT_QUERY_PAGE_SIZE,
    DEFAULT_QUERY_TIMEOUT_SECONDS,
    MAX_CURSOR_LENGTH,
    MAX_QUERY_DEPTH,
    MAX_QUERY_NODES,
    BoundedPathsRequest,
    ContainmentDirection,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphPathResult,
    GraphReadScope,
    GraphRelationshipKind,
    GraphSubgraph,
    GraphWindowRequest,
    NeighborhoodRequest,
    NodeDetailRequest,
    TraversalDirection,
)

SECRET = get_settings().internal_api_secret_key.get_secret_value()
PROJECT_ID = uuid4()
VERSION_ID = uuid4()
ENTITY_ID = uuid4()
TARGET_ENTITY_ID = uuid4()


@pytest.fixture(autouse=True)
def _setup_graph_service_overrides() -> Any:
    mock_query = _RecordingQueryService()
    mock_api = _RecordingApiService()
    app.dependency_overrides[get_graph_query_service] = lambda: mock_query
    app.dependency_overrides[get_graph_api_service] = lambda: mock_api
    yield
    app.dependency_overrides.pop(get_graph_query_service, None)
    app.dependency_overrides.pop(get_graph_api_service, None)


def _headers(project_id: UUID = PROJECT_ID, role: str = "DEVELOPER") -> dict[str, str]:
    return {
        "X-Service-Token": SECRET,
        "X-Actor-Id": str(uuid4()),
        "X-Actor-Role": role,
        "X-Project-Id": str(project_id),
    }


def _sample_scope() -> GraphReadScope:
    return GraphReadScope(
        project_id=PROJECT_ID,
        architecture_version_id=VERSION_ID,
        generation_id=uuid4(),
        resource_state="COMPLETED",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        counts=ProjectionCounts(
            entities=10,
            relationships=5,
            evidence=2,
            unresolved=0,
            conflicts=0,
        ),
    )


def _sample_node(
    entity_id: UUID = ENTITY_ID,
    name: str = "OrderService",
) -> GraphNode:
    return GraphNode(
        architecture_entity_id=entity_id,
        logical_id="architecture://service/order",
        canonical_kind="service",
        name=name,
        namespace="services",
        fact_status="confirmed",
        semantic_signature="sig-order-service",
        evidence_logical_ids=("evidence://safe",),
        metadata={"tier": "backend"},
    )


def _sample_edge(
    source_id: UUID = ENTITY_ID,
    target_id: UUID = TARGET_ENTITY_ID,
) -> GraphEdge:
    return GraphEdge(
        architecture_relationship_id=uuid4(),
        logical_id="architecture://rel/order-calls",
        canonical_kind="calls",
        status="confirmed",
        source_entity_id=source_id,
        target_entity_id=target_id,
        evidence_logical_ids=("evidence://safe-rel",),
        metadata={"protocol": "grpc"},
    )


class _RecordingQueryService:
    def __init__(self) -> None:
        self.last_method: str | None = None
        self.last_request: Any = None

    def get_node_detail(self, request: NodeDetailRequest) -> GraphNode:
        self.last_method = "get_node_detail"
        self.last_request = request
        return _sample_node(entity_id=request.entity_id)

    def get_window(self, request: GraphWindowRequest) -> GraphSubgraph:
        self.last_method = "get_window"
        self.last_request = request
        node = _sample_node()
        edge = _sample_edge()
        return GraphSubgraph(
            scope=_sample_scope(),
            nodes=(node,),
            edges=(edge,),
            total_manifest_nodes=1,
            total_manifest_edges=1,
            loaded_nodes=1,
            loaded_edges=1,
            next_cursor=None,
            truncated=False,
        )

    def get_neighborhood(self, request: NeighborhoodRequest) -> GraphSubgraph:
        self.last_method = "get_neighborhood"
        self.last_request = request
        node = _sample_node(request.entity_id)
        return GraphSubgraph(
            scope=_sample_scope(),
            nodes=(node,),
            edges=(),
            total_manifest_nodes=1,
            total_manifest_edges=0,
            loaded_nodes=1,
            loaded_edges=0,
            next_cursor=None,
            truncated=False,
        )

    def get_dependencies(self, request: DependenciesRequest) -> GraphSubgraph:
        self.last_method = "get_dependencies"
        self.last_request = request
        node = _sample_node(request.entity_id)
        return GraphSubgraph(
            scope=_sample_scope(),
            nodes=(node,),
            edges=(),
            total_manifest_nodes=1,
            total_manifest_edges=0,
            loaded_nodes=1,
            loaded_edges=0,
            next_cursor=None,
            truncated=False,
        )

    def get_dependents(self, request: DependentsRequest) -> GraphSubgraph:
        self.last_method = "get_dependents"
        self.last_request = request
        node = _sample_node(request.entity_id)
        return GraphSubgraph(
            scope=_sample_scope(),
            nodes=(node,),
            edges=(),
            total_manifest_nodes=1,
            total_manifest_edges=0,
            loaded_nodes=1,
            loaded_edges=0,
            next_cursor=None,
            truncated=False,
        )

    def get_containment(self, request: ContainmentRequest) -> GraphSubgraph:
        self.last_method = "get_containment"
        self.last_request = request
        node = _sample_node(request.entity_id)
        return GraphSubgraph(
            scope=_sample_scope(),
            nodes=(node,),
            edges=(),
            total_manifest_nodes=1,
            total_manifest_edges=0,
            loaded_nodes=1,
            loaded_edges=0,
            next_cursor=None,
            truncated=False,
        )

    def get_bounded_paths(self, request: BoundedPathsRequest) -> GraphPathResult:
        self.last_method = "get_bounded_paths"
        self.last_request = request
        path = GraphPath(
            nodes=(
                _sample_node(request.source_entity_id),
                _sample_node(request.target_entity_id),
            ),
            edges=(_sample_edge(request.source_entity_id, request.target_entity_id),),
            hop_count=1,
        )
        return GraphPathResult(
            scope=_sample_scope(),
            paths=(path,),
            total_paths_found=1,
            truncated=False,
        )


class _RecordingApiService:
    def __init__(
        self,
        status_result: ProjectionStatusResponse | None = None,
        rebuild_result: ProjectionRebuildAcceptedResponse | None = None,
    ) -> None:
        self.status_result = status_result
        self.rebuild_result = rebuild_result
        self.last_status_call: tuple[UUID, UUID, str] | None = None
        self.last_rebuild_call: tuple[UUID, UUID, UUID, str, str, str] | None = None

    def get_status(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        projection_type: str = PROJECTION_TYPE,
    ) -> ProjectionStatusResponse | None:
        self.last_status_call = (project_id, architecture_version_id, projection_type)
        return self.status_result

    def request_rebuild(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        actor_id: UUID,
        actor_role: str,
        correlation_id: str,
        projection_type: str = PROJECTION_TYPE,
    ) -> ProjectionRebuildAcceptedResponse:
        self.last_rebuild_call = (
            project_id,
            architecture_version_id,
            actor_id,
            actor_role,
            correlation_id,
            projection_type,
        )
        now = datetime.now(UTC)
        return (
            self.rebuild_result
            if self.rebuild_result is not None
            else ProjectionRebuildAcceptedResponse(
                resource_id=uuid4(),
                architecture_version_id=architecture_version_id,
                status="PENDING",
                attempt_id=uuid4(),
                attempt_number=1,
                attempt_status="QUEUED",
                accepted_at=now,
            )
        )


def test_contract_version_and_dto_serialization() -> None:
    assert P4_D1_CONTRACT_VERSION == "1.0.0"

    now = datetime.now(UTC)
    attempt_id = uuid4()
    attempt = ProjectionAttemptSummary(
        attempt_id=attempt_id,
        attempt_number=1,
        status="RUNNING",
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    assert attempt.attempt_id == attempt_id
    assert attempt.status == "RUNNING"

    # extra='forbid' test
    with pytest.raises(ValidationError):
        ProjectionAttemptSummary(
            attempt_id=attempt_id,
            attempt_number=1,
            status="RUNNING",
            created_at=now,
            updated_at=now,
            extra_field="disallowed",  # type: ignore[call-arg]
        )

    counts = ProjectionCounts(
        entities=10,
        relationships=20,
        evidence=5,
        unresolved=2,
        conflicts=0,
    )
    status_resp = ProjectionStatusResponse(
        resource_id=uuid4(),
        project_id=PROJECT_ID,
        architecture_version_id=VERSION_ID,
        projection_type=PROJECTION_TYPE,
        status="COMPLETED",
        active_generation_id=uuid4(),
        schema_version="1.0.0",
        projector_version="1.0.0",
        counts=counts,
        created_at=now,
        updated_at=now,
        last_attempt_at=now,
        active_attempt=attempt,
    )
    data = status_resp.model_dump()
    assert data["status"] == "COMPLETED"
    assert data["counts"]["entities"] == 10
    assert data["active_attempt"]["attempt_number"] == 1

    accepted_resp = ProjectionRebuildAcceptedResponse(
        resource_id=uuid4(),
        architecture_version_id=VERSION_ID,
        status="PENDING",
        attempt_id=attempt_id,
        attempt_number=2,
        attempt_status="QUEUED",
        accepted_at=now,
    )
    assert accepted_resp.attempt_status == "QUEUED"

    error_resp = GraphErrorResponse(
        error={
            "code": "graph_node_not_found",
            "message": "Node not found",
            "details": {"entity_id": str(ENTITY_ID)},
        }
    )
    assert error_resp.error.code == "graph_node_not_found"


def test_openapi_contains_graph_paths_and_models() -> None:
    schema = app.openapi()
    paths = schema["paths"]

    expected_endpoints = [
        "/api/v1/architecture-versions/{version_id}/graph/status",
        "/api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}",
        "/api/v1/architecture-versions/{version_id}/graph/window",
        "/api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}/neighborhood",
        "/api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}/dependencies",
        "/api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}/dependents",
        "/api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}/containment",
        "/api/v1/architecture-versions/{version_id}/graph/paths",
    ]

    for ep in expected_endpoints:
        assert ep in paths, f"Missing OpenAPI endpoint: {ep}"
        assert "get" in paths[ep], f"Missing GET method for: {ep}"
        responses = paths[ep]["get"]["responses"]
        assert "200" in responses
        assert "400" not in responses
        assert "401" in responses
        assert "403" in responses
        assert "404" in responses
        assert "422" in responses

    # 1. Rebuild endpoint
    rebuild_ep = "/api/v1/architecture-versions/{version_id}/graph/rebuild"
    assert rebuild_ep in paths
    assert "post" in paths[rebuild_ep]
    rebuild_responses = paths[rebuild_ep]["post"]["responses"]
    assert "202" in rebuild_responses
    assert "400" not in rebuild_responses
    assert "401" in rebuild_responses
    assert "403" in rebuild_responses
    assert "404" in rebuild_responses
    assert "422" in rebuild_responses

    # 2. Query health endpoint
    health_ep = "/api/v1/health/graph/query"
    assert health_ep in paths
    assert "get" in paths[health_ep]
    assert "200" in paths[health_ep]["get"]["responses"]

    # 3. Schemas
    schemas = schema["components"]["schemas"]
    assert "ProjectionRebuildAcceptedResponse" in schemas
    assert "GraphQueryHealthResponse" in schemas


def test_get_projection_status_mapping() -> None:
    now = datetime.now(UTC)
    resource_id = uuid4()
    mock_status = ProjectionStatusResponse(
        resource_id=resource_id,
        project_id=PROJECT_ID,
        architecture_version_id=VERSION_ID,
        projection_type=PROJECTION_TYPE,
        status="COMPLETED",
        created_at=now,
        updated_at=now,
    )
    api_service = _RecordingApiService(status_result=mock_status)
    app.dependency_overrides[get_graph_api_service] = lambda: api_service

    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
            params={"project_id": str(PROJECT_ID)},
            headers=_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["resource_id"] == str(resource_id)
        assert data["status"] == "COMPLETED"
        assert api_service.last_status_call == (
            PROJECT_ID,
            VERSION_ID,
            PROJECTION_TYPE,
        )

        # Not found test
        api_service.status_result = None
        not_found_response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
            params={"project_id": str(PROJECT_ID)},
            headers=_headers(),
        )
        assert not_found_response.status_code == 404
        err = not_found_response.json()["error"]
        assert err["code"] == "graph_projection_not_found"
    finally:
        client.close()


def test_rebuild_mapping() -> None:
    now = datetime.now(UTC)
    resource_id = uuid4()
    attempt_id = uuid4()
    mock_rebuild = ProjectionRebuildAcceptedResponse(
        resource_id=resource_id,
        architecture_version_id=VERSION_ID,
        status="PENDING",
        attempt_id=attempt_id,
        attempt_number=1,
        attempt_status="QUEUED",
        accepted_at=now,
    )
    api_service = _RecordingApiService(rebuild_result=mock_rebuild)
    app.dependency_overrides[get_graph_api_service] = lambda: api_service

    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/rebuild",
            params={"project_id": str(PROJECT_ID)},
            headers=_headers(role="OWNER"),
        )
        assert response.status_code == 202
        data = response.json()
        assert data["resource_id"] == str(resource_id)
        assert data["architecture_version_id"] == str(VERSION_ID)
        assert data["status"] == "PENDING"
        assert data["attempt_id"] == str(attempt_id)
        assert data["attempt_number"] == 1
        assert data["attempt_status"] == "QUEUED"

        assert api_service.last_rebuild_call is not None
        assert api_service.last_rebuild_call[0] == PROJECT_ID
        assert api_service.last_rebuild_call[1] == VERSION_ID
        assert api_service.last_rebuild_call[3] == "OWNER"
        assert api_service.last_rebuild_call[5] == PROJECTION_TYPE
    finally:
        client.close()


def test_sqlalchemy_graph_projection_status_reader_seeded_model() -> None:
    """Verify SqlAlchemyGraphProjectionStatusReader against M1 persistence models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            GraphProjectionResourceModel.__table__,
            GraphProjectionAttemptModel.__table__,
        ],
    )

    session = Session(engine)
    res_id = uuid4()
    ver_id = uuid4()
    proj_id = uuid4()
    rep_id = uuid4()
    gen_id = uuid4()
    att_id = uuid4()
    now = datetime.now(UTC)

    resource = GraphProjectionResourceModel(
        id=res_id,
        architecture_version_id=ver_id,
        project_id=proj_id,
        repository_id=rep_id,
        architecture_sequence=1,
        projection_type=PROJECTION_TYPE,
        source_content_digest="abc",
        source_schema_version="1.0",
        state=ProjectionPublicState.COMPLETED.value,
        active_generation_id=gen_id,
        active_projector_version="1.0.0",
        active_graph_schema_version="1.0.0",
        active_payload_digest="payload-digest-123",
        active_entity_count=42,
        active_relationship_count=10,
        active_evidence_count=5,
        active_unresolved_count=1,
        active_conflict_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(resource)

    attempt = GraphProjectionAttemptModel(
        id=att_id,
        resource_id=res_id,
        generation_id=gen_id,
        attempt_number=1,
        state=ProjectionAttemptState.QUEUED.value,
        actor_type="SYSTEM",
        actor_id=None,
        actor_role=None,
        correlation_id="test-corr-id",
        contract_version="1.0.0",
        source_content_digest="abc",
        source_schema_version="1.0",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        expected_entity_count=42,
        expected_relationship_count=10,
        expected_evidence_count=5,
        expected_unresolved_count=1,
        expected_conflict_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(attempt)
    session.commit()

    try:
        reader = SqlAlchemyGraphProjectionStatusReader(session)

        # 1. Exact scope matches
        status = reader.get_status(
            project_id=proj_id,
            architecture_version_id=ver_id,
        )
        assert status is not None
        assert status.resource_id == res_id
        assert status.project_id == proj_id
        assert status.architecture_version_id == ver_id
        assert status.projection_type == PROJECTION_TYPE
        assert status.status == "COMPLETED"
        assert status.counts is not None
        assert status.counts.entities == 42
        assert status.counts.relationships == 10
        assert status.active_attempt is not None
        assert status.active_attempt.attempt_id == att_id
        assert status.active_attempt.status == "QUEUED"
        assert status.last_attempt_at is not None
        assert status.last_attempt_at.replace(tzinfo=UTC) == now

        # 2. Out of scope returns None
        wrong_proj = reader.get_status(
            project_id=uuid4(),
            architecture_version_id=ver_id,
        )
        assert wrong_proj is None

        wrong_ver = reader.get_status(
            project_id=proj_id,
            architecture_version_id=uuid4(),
        )
        assert wrong_ver is None
    finally:
        session.close()
        engine.dispose()


def test_get_node_detail_mapping() -> None:
    query_service = _RecordingQueryService()
    app.dependency_overrides[get_graph_query_service] = lambda: query_service

    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}",
            params={"project_id": str(PROJECT_ID), "timeout_seconds": 3.5},
            headers=_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["architecture_entity_id"] == str(ENTITY_ID)
        assert data["name"] == "OrderService"

        req: NodeDetailRequest = query_service.last_request
        assert req.project_id == PROJECT_ID
        assert req.architecture_version_id == VERSION_ID
        assert req.entity_id == ENTITY_ID
        assert req.timeout_seconds == 3.5
    finally:
        client.close()


def test_get_graph_window_mapping_and_defaults() -> None:
    query_service = _RecordingQueryService()
    app.dependency_overrides[get_graph_query_service] = lambda: query_service

    client = TestClient(app)
    try:
        # Default parameters
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params={"project_id": str(PROJECT_ID)},
            headers=_headers(),
        )
        assert response.status_code == 200
        req: GraphWindowRequest = query_service.last_request
        assert req.node_limit == DEFAULT_QUERY_NODES
        assert req.edge_limit == DEFAULT_QUERY_EDGES
        assert req.page_size == DEFAULT_QUERY_PAGE_SIZE
        assert req.canonical_kinds is None
        assert req.cursor is None
        assert req.timeout_seconds == DEFAULT_QUERY_TIMEOUT_SECONDS

        # Explicit and repeated parameters
        response_explicit = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params=[
                ("project_id", str(PROJECT_ID)),
                ("node_limit", "50"),
                ("edge_limit", "100"),
                ("page_size", "25"),
                ("canonical_kinds", "calls"),
                ("canonical_kinds", "depends_on"),
                ("cursor", "opaque-cursor-token"),
                ("timeout_seconds", "4.0"),
            ],
            headers=_headers(),
        )
        assert response_explicit.status_code == 200
        req_exp: GraphWindowRequest = query_service.last_request
        assert req_exp.node_limit == 50
        assert req_exp.edge_limit == 100
        assert req_exp.page_size == 25
        assert req_exp.canonical_kinds == (
            GraphRelationshipKind.CALLS,
            GraphRelationshipKind.DEPENDS_ON,
        )
        assert req_exp.cursor == "opaque-cursor-token"
        assert req_exp.timeout_seconds == 4.0
    finally:
        client.close()


def test_get_neighborhood_mapping() -> None:
    query_service = _RecordingQueryService()
    app.dependency_overrides[get_graph_query_service] = lambda: query_service

    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/neighborhood",
            params=[
                ("project_id", str(PROJECT_ID)),
                ("direction", "incoming"),
                ("depth", "2"),
                ("node_limit", "60"),
                ("relationship_kinds", "calls"),
            ],
            headers=_headers(),
        )
        assert response.status_code == 200
        req: NeighborhoodRequest = query_service.last_request
        assert req.entity_id == ENTITY_ID
        assert req.direction == TraversalDirection.INCOMING
        assert req.depth == 2
        assert req.node_limit == 60
        assert req.relationship_kinds == (GraphRelationshipKind.CALLS,)
    finally:
        client.close()


def test_get_dependencies_and_dependents_mapping() -> None:
    query_service = _RecordingQueryService()
    app.dependency_overrides[get_graph_query_service] = lambda: query_service

    client = TestClient(app)
    try:
        resp_deps = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/dependencies",
            params=[
                ("project_id", str(PROJECT_ID)),
                ("depth", "3"),
                ("relationship_kinds", "depends_on"),
            ],
            headers=_headers(),
        )
        assert resp_deps.status_code == 200
        req_deps: DependenciesRequest = query_service.last_request
        assert req_deps.depth == 3
        assert req_deps.relationship_kinds == (GraphRelationshipKind.DEPENDS_ON,)

        resp_depnts = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/dependents",
            params=[
                ("project_id", str(PROJECT_ID)),
                ("depth", "2"),
                ("relationship_kinds", "calls"),
            ],
            headers=_headers(),
        )
        assert resp_depnts.status_code == 200
        req_depnts: DependentsRequest = query_service.last_request
        assert req_depnts.depth == 2
        assert req_depnts.relationship_kinds == (GraphRelationshipKind.CALLS,)

        # Permitted-only rules: 'contains' is forbidden in dependencies
        resp_forbidden_kind = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/dependencies",
            params=[
                ("project_id", str(PROJECT_ID)),
                ("relationship_kinds", "contains"),
            ],
            headers=_headers(),
        )
        assert resp_forbidden_kind.status_code == 422
        err = resp_forbidden_kind.json()["error"]
        assert err["code"] == "graph_query_limit_exceeded"
    finally:
        client.close()


def test_get_containment_mapping() -> None:
    query_service = _RecordingQueryService()
    app.dependency_overrides[get_graph_query_service] = lambda: query_service

    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/containment",
            params=[
                ("project_id", str(PROJECT_ID)),
                ("direction", "parents"),
                ("depth", "4"),
            ],
            headers=_headers(),
        )
        assert response.status_code == 200
        req: ContainmentRequest = query_service.last_request
        assert req.entity_id == ENTITY_ID
        assert req.direction == ContainmentDirection.PARENTS
        assert req.depth == 4
    finally:
        client.close()


def test_get_bounded_paths_mapping() -> None:
    query_service = _RecordingQueryService()
    app.dependency_overrides[get_graph_query_service] = lambda: query_service

    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/paths",
            params=[
                ("project_id", str(PROJECT_ID)),
                ("source_entity_id", str(ENTITY_ID)),
                ("target_entity_id", str(TARGET_ENTITY_ID)),
                ("max_depth", "4"),
                ("path_limit", "10"),
                ("relationship_kinds", "calls"),
            ],
            headers=_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["paths"]) == 1

        req: BoundedPathsRequest = query_service.last_request
        assert req.source_entity_id == ENTITY_ID
        assert req.target_entity_id == TARGET_ENTITY_ID
        assert req.max_depth == 4
        assert req.path_limit == 10
        assert req.relationship_kinds == (GraphRelationshipKind.CALLS,)
    finally:
        client.close()


def test_parameter_bounds_and_invalid_values() -> None:
    client = TestClient(app)
    try:
        # Node limit exceeding maximum
        resp_over_nodes = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params={"project_id": str(PROJECT_ID), "node_limit": MAX_QUERY_NODES + 1},
            headers=_headers(),
        )
        assert resp_over_nodes.status_code == 422

        # Depth exceeding maximum
        resp_over_depth = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/neighborhood",
            params={"project_id": str(PROJECT_ID), "depth": MAX_QUERY_DEPTH + 1},
            headers=_headers(),
        )
        assert resp_over_depth.status_code == 422

        # Invalid enum string
        resp_bad_enum = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/neighborhood",
            params={"project_id": str(PROJECT_ID), "direction": "diagonal"},
            headers=_headers(),
        )
        assert resp_bad_enum.status_code == 422

        # Overlong cursor
        resp_long_cursor = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params={
                "project_id": str(PROJECT_ID),
                "cursor": "x" * (MAX_CURSOR_LENGTH + 1),
            },
            headers=_headers(),
        )
        assert resp_long_cursor.status_code == 422
    finally:
        client.close()


def test_query_health_endpoint() -> None:
    from backend.platform.graph.dependencies import get_graph_query_health_probe
    from backend.platform.graph.query_health import (
        GraphQueryHealthResponse,
        GraphQueryHealthStatus,
    )

    class _MockProbe:
        def check(self) -> GraphQueryHealthResponse:
            return GraphQueryHealthResponse(
                status=GraphQueryHealthStatus.READY,
                code="query_engine_ready",
                details=None,
            )

    app.dependency_overrides[get_graph_query_health_probe] = _MockProbe
    client = TestClient(app)
    try:
        # Unauthenticated request to query health
        response = client.get("/api/v1/health/graph/query")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["code"] == "query_engine_ready"
    finally:
        app.dependency_overrides.pop(get_graph_query_health_probe, None)
        client.close()


def test_graph_api_service_request_rebuild_unit() -> None:
    from unittest.mock import MagicMock

    from backend.platform.graph.api_service import GraphApiService

    status_reader = MagicMock()
    lifecycle = MagicMock()
    commit_mock = MagicMock()
    rollback_mock = MagicMock()

    res_id = uuid4()
    proj_id = uuid4()
    ver_id = uuid4()
    att_id = uuid4()
    now = datetime.now(UTC)

    mock_status_before = ProjectionStatusResponse(
        resource_id=res_id,
        project_id=proj_id,
        architecture_version_id=ver_id,
        projection_type=PROJECTION_TYPE,
        status="COMPLETED",
        created_at=now,
        updated_at=now,
    )
    mock_status_after = ProjectionStatusResponse(
        resource_id=res_id,
        project_id=proj_id,
        architecture_version_id=ver_id,
        projection_type=PROJECTION_TYPE,
        status="PENDING",
        created_at=now,
        updated_at=now,
        active_attempt=ProjectionAttemptSummary(
            attempt_id=att_id,
            attempt_number=2,
            status="QUEUED",
            created_at=now,
            updated_at=now,
        ),
    )
    status_reader.get_status.side_effect = [
        mock_status_before,
        mock_status_after,
    ]

    mock_attempt = MagicMock()
    mock_attempt.id = att_id
    mock_attempt.attempt_number = 2
    mock_attempt.state = ProjectionAttemptState.QUEUED
    mock_attempt.created_at = now
    lifecycle.request_rebuild.return_value = (mock_attempt, MagicMock())

    service = GraphApiService(
        status_reader=status_reader,
        lifecycle=lifecycle,
        commit_fn=commit_mock,
        rollback_fn=rollback_mock,
    )

    result = service.request_rebuild(
        project_id=proj_id,
        architecture_version_id=ver_id,
        actor_id=uuid4(),
        actor_role="OWNER",
        correlation_id="test-corr",
    )

    assert result.resource_id == res_id
    assert result.attempt_id == att_id
    assert result.attempt_number == 2
    assert result.attempt_status == "QUEUED"
    assert commit_mock.call_count == 1
    assert rollback_mock.call_count == 0


def test_graph_api_service_request_rebuild_commit_failure_rollback() -> None:
    from unittest.mock import MagicMock

    from sqlalchemy.exc import OperationalError

    from backend.platform.graph.api_contracts import (
        GraphLifecycleUnavailableError,
    )
    from backend.platform.graph.api_service import GraphApiService

    status_reader = MagicMock()
    lifecycle = MagicMock()
    commit_mock = MagicMock(side_effect=OperationalError("db error", {}, Exception()))
    rollback_mock = MagicMock()

    res_id = uuid4()
    proj_id = uuid4()
    ver_id = uuid4()
    now = datetime.now(UTC)

    status_reader.get_status.return_value = ProjectionStatusResponse(
        resource_id=res_id,
        project_id=proj_id,
        architecture_version_id=ver_id,
        projection_type=PROJECTION_TYPE,
        status="COMPLETED",
        created_at=now,
        updated_at=now,
    )
    lifecycle.request_rebuild.return_value = (MagicMock(), MagicMock())

    service = GraphApiService(
        status_reader=status_reader,
        lifecycle=lifecycle,
        commit_fn=commit_mock,
        rollback_fn=rollback_mock,
    )

    with pytest.raises(GraphLifecycleUnavailableError):
        service.request_rebuild(
            project_id=proj_id,
            architecture_version_id=ver_id,
            actor_id=uuid4(),
            actor_role="ADMIN",
            correlation_id="test-corr",
        )

    assert commit_mock.call_count == 1
    assert rollback_mock.call_count == 1


def test_graph_api_service_request_rebuild_lifecycle_state_error_mapping() -> None:
    from unittest.mock import MagicMock

    from backend.platform.graph.api_contracts import GraphRebuildConflictError
    from backend.platform.graph.api_service import GraphApiService
    from backend.platform.graph.repository import GraphLifecycleStateError

    status_reader = MagicMock()
    lifecycle = MagicMock()
    lifecycle.request_rebuild.side_effect = GraphLifecycleStateError(
        "internal state raw error details"
    )
    commit_mock = MagicMock()
    rollback_mock = MagicMock()

    res_id = uuid4()
    proj_id = uuid4()
    ver_id = uuid4()
    now = datetime.now(UTC)

    status_reader.get_status.return_value = ProjectionStatusResponse(
        resource_id=res_id,
        project_id=proj_id,
        architecture_version_id=ver_id,
        projection_type=PROJECTION_TYPE,
        status="COMPLETED",
        created_at=now,
        updated_at=now,
    )

    service = GraphApiService(
        status_reader=status_reader,
        lifecycle=lifecycle,
        commit_fn=commit_mock,
        rollback_fn=rollback_mock,
    )

    with pytest.raises(GraphRebuildConflictError) as exc_info:
        service.request_rebuild(
            project_id=proj_id,
            architecture_version_id=ver_id,
            actor_id=uuid4(),
            actor_role="ADMIN",
            correlation_id="test-corr",
        )

    assert exc_info.value.code == "graph_rebuild_conflict"
    assert exc_info.value.message == "Graph projection rebuild conflict"
    assert "internal state raw error details" not in str(exc_info.value)
    assert rollback_mock.call_count == 1
    assert commit_mock.call_count == 0


def test_graph_api_service_request_rebuild_unexpected_error_mapping() -> None:
    from unittest.mock import MagicMock

    from backend.platform.graph.api_contracts import GraphApiInternalError
    from backend.platform.graph.api_service import GraphApiService

    status_reader = MagicMock()
    lifecycle = MagicMock()
    lifecycle.request_rebuild.side_effect = RuntimeError(
        "unexpected internal exception"
    )
    commit_mock = MagicMock()
    rollback_mock = MagicMock()

    res_id = uuid4()
    proj_id = uuid4()
    ver_id = uuid4()
    now = datetime.now(UTC)

    status_reader.get_status.return_value = ProjectionStatusResponse(
        resource_id=res_id,
        project_id=proj_id,
        architecture_version_id=ver_id,
        projection_type=PROJECTION_TYPE,
        status="COMPLETED",
        created_at=now,
        updated_at=now,
    )

    service = GraphApiService(
        status_reader=status_reader,
        lifecycle=lifecycle,
        commit_fn=commit_mock,
        rollback_fn=rollback_mock,
    )

    with pytest.raises(GraphApiInternalError) as exc_info:
        service.request_rebuild(
            project_id=proj_id,
            architecture_version_id=ver_id,
            actor_id=uuid4(),
            actor_role="ADMIN",
            correlation_id="test-corr",
        )

    assert exc_info.value.code == "graph_api_internal_error"
    assert exc_info.value.message == "Internal graph API error"
    assert rollback_mock.call_count == 1
    assert commit_mock.call_count == 0


def test_graph_api_service_request_rebuild_sqlite_attempt_reuse() -> None:
    """Test GraphApiService against SQLite models proving attempt reuse."""
    from backend.platform.graph.api_service import (
        GraphApiService,
        SqlAlchemyGraphProjectionStatusReader,
    )
    from backend.platform.graph.lifecycle import GraphProjectionLifecycle
    from backend.platform.graph.persistence import (
        SqlAlchemyGraphProjectionRepository,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            GraphProjectionResourceModel.__table__,
            GraphProjectionAttemptModel.__table__,
        ],
    )

    session = Session(engine)
    res_id = uuid4()
    ver_id = uuid4()
    proj_id = uuid4()
    rep_id = uuid4()
    gen_id = uuid4()
    att_id = uuid4()
    actor_id = uuid4()
    now = datetime.now(UTC)

    resource = GraphProjectionResourceModel(
        id=res_id,
        architecture_version_id=ver_id,
        project_id=proj_id,
        repository_id=rep_id,
        architecture_sequence=1,
        projection_type=PROJECTION_TYPE,
        source_content_digest="abc",
        source_schema_version="1.0",
        state=ProjectionPublicState.COMPLETED.value,
        active_generation_id=gen_id,
        active_projector_version="1.0.0",
        active_graph_schema_version="1.0.0",
        active_payload_digest="digest-123",
        active_entity_count=42,
        active_relationship_count=10,
        active_evidence_count=5,
        active_unresolved_count=1,
        active_conflict_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(resource)

    initial_attempt = GraphProjectionAttemptModel(
        id=att_id,
        resource_id=res_id,
        generation_id=gen_id,
        attempt_number=1,
        state=ProjectionAttemptState.COMPLETED.value,
        actor_type="SYSTEM",
        actor_id=None,
        actor_role=None,
        correlation_id="init-corr",
        contract_version="1.0.0",
        source_content_digest="abc",
        source_schema_version="1.0",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        expected_entity_count=42,
        expected_relationship_count=10,
        expected_evidence_count=5,
        expected_unresolved_count=1,
        expected_conflict_count=0,
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    session.add(initial_attempt)
    session.commit()

    try:
        repo = SqlAlchemyGraphProjectionRepository(session)
        lifecycle = GraphProjectionLifecycle(repo)
        status_reader = SqlAlchemyGraphProjectionStatusReader(session)
        service = GraphApiService(
            status_reader=status_reader,
            lifecycle=lifecycle,
            commit_fn=session.commit,
            rollback_fn=session.rollback,
        )

        # 1. First rebuild request creates attempt #2 (QUEUED)
        resp1 = service.request_rebuild(
            project_id=proj_id,
            architecture_version_id=ver_id,
            actor_id=actor_id,
            actor_role="OWNER",
            correlation_id="corr-1",
        )
        assert resp1.resource_id == res_id
        assert resp1.attempt_number == 2
        assert resp1.attempt_status == "QUEUED"

        # 2. Second rebuild request while attempt #2 is active REUSES attempt #2!
        resp2 = service.request_rebuild(
            project_id=proj_id,
            architecture_version_id=ver_id,
            actor_id=actor_id,
            actor_role="ADMIN",
            correlation_id="corr-2",
        )
        assert resp2.resource_id == res_id
        assert resp2.attempt_id == resp1.attempt_id
        assert resp2.attempt_number == 2
        assert resp2.attempt_status == "QUEUED"

        # Verify only 2 attempts in database table (1 initial + 1 active rebuild)
        attempts = session.query(GraphProjectionAttemptModel).all()
        assert len(attempts) == 2
    finally:
        session.close()
        engine.dispose()
