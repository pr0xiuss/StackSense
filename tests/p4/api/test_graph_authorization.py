"""P4-D1 Graph API delegated authentication and authorization tests."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.platform.config import get_settings
from backend.platform.graph.api_contracts import (
    ProjectionRebuildAcceptedResponse,
    ProjectionStatusResponse,
)
from backend.platform.graph.api_dependencies import get_graph_api_service
from backend.platform.graph.dependencies import get_graph_query_service
from backend.platform.graph.model import PROJECTION_TYPE, ProjectionCounts
from backend.platform.graph.query_contracts import (
    BoundedPathsRequest,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphNode,
    GraphPathResult,
    GraphReadScope,
    GraphSubgraph,
    GraphWindowRequest,
    NeighborhoodRequest,
    NodeDetailRequest,
)

SECRET = get_settings().internal_api_secret_key.get_secret_value()
PROJECT_ID = uuid4()
VERSION_ID = uuid4()
ENTITY_ID = uuid4()
TARGET_ENTITY_ID = uuid4()


@pytest.fixture(autouse=True)
def _setup_graph_service_overrides() -> Any:
    mock_query = _MockQueryService()
    mock_api = _MockApiService()
    app.dependency_overrides[get_graph_query_service] = lambda: mock_query
    app.dependency_overrides[get_graph_api_service] = lambda: mock_api
    yield
    app.dependency_overrides.pop(get_graph_query_service, None)
    app.dependency_overrides.pop(get_graph_api_service, None)


def _auth_sample_scope() -> GraphReadScope:
    return GraphReadScope(
        project_id=PROJECT_ID,
        architecture_version_id=VERSION_ID,
        generation_id=uuid4(),
        resource_state="COMPLETED",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        counts=ProjectionCounts(
            entities=1,
            relationships=0,
            evidence=0,
            unresolved=0,
            conflicts=0,
        ),
    )


class _MockQueryService:
    def __init__(self) -> None:
        self.call_count = 0

    def get_node_detail(self, request: NodeDetailRequest) -> GraphNode:
        self.call_count += 1
        return GraphNode(
            architecture_entity_id=request.entity_id,
            logical_id="architecture://service/test",
            canonical_kind="service",
            name="TestService",
            namespace="default",
            fact_status="confirmed",
            semantic_signature="sig-test",
            evidence_logical_ids=(),
            metadata={},
        )

    def get_window(self, request: GraphWindowRequest) -> GraphSubgraph:
        self.call_count += 1
        return GraphSubgraph(
            scope=_auth_sample_scope(),
            nodes=(),
            edges=(),
            total_manifest_nodes=0,
            total_manifest_edges=0,
            loaded_nodes=0,
            loaded_edges=0,
            next_cursor=None,
            truncated=False,
        )

    def get_neighborhood(self, request: NeighborhoodRequest) -> GraphSubgraph:
        self.call_count += 1
        return GraphSubgraph(
            scope=_auth_sample_scope(),
            nodes=(),
            edges=(),
            total_manifest_nodes=0,
            total_manifest_edges=0,
            loaded_nodes=0,
            loaded_edges=0,
            next_cursor=None,
            truncated=False,
        )

    def get_dependencies(self, request: DependenciesRequest) -> GraphSubgraph:
        self.call_count += 1
        return GraphSubgraph(
            scope=_auth_sample_scope(),
            nodes=(),
            edges=(),
            total_manifest_nodes=0,
            total_manifest_edges=0,
            loaded_nodes=0,
            loaded_edges=0,
            next_cursor=None,
            truncated=False,
        )

    def get_dependents(self, request: DependentsRequest) -> GraphSubgraph:
        self.call_count += 1
        return GraphSubgraph(
            scope=_auth_sample_scope(),
            nodes=(),
            edges=(),
            total_manifest_nodes=0,
            total_manifest_edges=0,
            loaded_nodes=0,
            loaded_edges=0,
            next_cursor=None,
            truncated=False,
        )

    def get_containment(self, request: ContainmentRequest) -> GraphSubgraph:
        self.call_count += 1
        return GraphSubgraph(
            scope=_auth_sample_scope(),
            nodes=(),
            edges=(),
            total_manifest_nodes=0,
            total_manifest_edges=0,
            loaded_nodes=0,
            loaded_edges=0,
            next_cursor=None,
            truncated=False,
        )

    def get_bounded_paths(self, request: BoundedPathsRequest) -> GraphPathResult:
        self.call_count += 1
        return GraphPathResult(
            scope=_auth_sample_scope(),
            paths=(),
            total_paths_found=0,
            truncated=False,
        )


class _MockApiService:
    def __init__(self) -> None:
        self.call_count = 0

    def get_status(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        projection_type: str = PROJECTION_TYPE,
    ) -> ProjectionStatusResponse | None:
        self.call_count += 1
        now = datetime.now(UTC)
        return ProjectionStatusResponse(
            resource_id=uuid4(),
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            projection_type=projection_type,
            status="COMPLETED",
            created_at=now,
            updated_at=now,
        )

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
        self.call_count += 1
        now = datetime.now(UTC)
        return ProjectionRebuildAcceptedResponse(
            resource_id=uuid4(),
            architecture_version_id=architecture_version_id,
            status="PENDING",
            attempt_id=uuid4(),
            attempt_number=1,
            attempt_status="QUEUED",
            accepted_at=now,
        )


def _valid_headers(
    *,
    project_id: UUID = PROJECT_ID,
    role: str = "DEVELOPER",
    correlation_id: str | None = None,
) -> dict[str, str]:
    headers = {
        "X-Service-Token": SECRET,
        "X-Actor-Id": str(uuid4()),
        "X-Actor-Role": role,
        "X-Project-Id": str(project_id),
    }
    if correlation_id is not None:
        headers["X-Correlation-Id"] = correlation_id
    return headers


def test_service_credential_required() -> None:
    client = TestClient(app)
    try:
        # Missing token entirely
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
            params={"project_id": str(PROJECT_ID)},
        )
        assert response.status_code == 401
        err = response.json()["error"]
        assert err["code"] == "authentication_required"

        # Invalid token
        response_bad = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
            params={"project_id": str(PROJECT_ID)},
            headers={
                "X-Service-Token": "invalid-secret-key",
                "X-Actor-Id": str(uuid4()),
                "X-Actor-Role": "ADMIN",
                "X-Project-Id": str(PROJECT_ID),
            },
        )
        assert response_bad.status_code == 401
        assert response_bad.json()["error"]["code"] == "invalid_token"
    finally:
        client.close()


def test_delegated_headers_validation() -> None:
    client = TestClient(app)
    try:
        # Missing actor and project headers
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
            params={"project_id": str(PROJECT_ID)},
            headers={"X-Service-Token": SECRET},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "analysis_input_invalid"

        # Malformed UUID in actor
        response_bad_actor = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
            params={"project_id": str(PROJECT_ID)},
            headers={
                "X-Service-Token": SECRET,
                "X-Actor-Id": "not-a-uuid",
                "X-Actor-Role": "ADMIN",
                "X-Project-Id": str(PROJECT_ID),
            },
        )
        assert response_bad_actor.status_code == 422
        assert response_bad_actor.json()["error"]["code"] == "analysis_input_invalid"

        # Unknown role
        response_bad_role = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
            params={"project_id": str(PROJECT_ID)},
            headers={
                "X-Service-Token": SECRET,
                "X-Actor-Id": str(uuid4()),
                "X-Actor-Role": "UNRECOGNIZED_ROLE",
                "X-Project-Id": str(PROJECT_ID),
            },
        )
        assert response_bad_role.status_code == 403
        assert response_bad_role.json()["error"]["code"] == "analysis_access_denied"
    finally:
        client.close()


def test_project_mismatch_denied_before_service_invocation() -> None:
    mock_query = _MockQueryService()
    mock_api = _MockApiService()
    app.dependency_overrides[get_graph_query_service] = lambda: mock_query
    app.dependency_overrides[get_graph_api_service] = lambda: mock_api

    client = TestClient(app)
    try:
        other_project_id = uuid4()
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params={"project_id": str(PROJECT_ID)},
            headers=_valid_headers(project_id=other_project_id),
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "analysis_access_denied"
        # Verify query service was never called
        assert mock_query.call_count == 0

        # Status endpoint mismatch
        response_status = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
            params={"project_id": str(PROJECT_ID)},
            headers=_valid_headers(project_id=other_project_id),
        )
        assert response_status.status_code == 403
        assert mock_api.call_count == 0
    finally:
        client.close()


@pytest.mark.parametrize("role", ["OWNER", "ADMIN", "DEVELOPER", "VIEWER"])
def test_all_roles_permitted_for_all_reads(role: str) -> None:
    mock_query = _MockQueryService()
    mock_api = _MockApiService()
    app.dependency_overrides[get_graph_query_service] = lambda: mock_query
    app.dependency_overrides[get_graph_api_service] = lambda: mock_api

    client = TestClient(app)
    try:
        headers = _valid_headers(role=role)

        # 1. Status
        r1 = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
            params={"project_id": str(PROJECT_ID)},
            headers=headers,
        )
        assert r1.status_code == 200

        # 2. Node detail
        r2 = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}",
            params={"project_id": str(PROJECT_ID)},
            headers=headers,
        )
        assert r2.status_code == 200

        # 3. Window
        r3 = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params={"project_id": str(PROJECT_ID)},
            headers=headers,
        )
        assert r3.status_code == 200

        # 4. Neighborhood
        r4 = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/neighborhood",
            params={"project_id": str(PROJECT_ID)},
            headers=headers,
        )
        assert r4.status_code == 200

        # 5. Dependencies
        r5 = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/dependencies",
            params={"project_id": str(PROJECT_ID)},
            headers=headers,
        )
        assert r5.status_code == 200

        # 6. Dependents
        r6 = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/dependents",
            params={"project_id": str(PROJECT_ID)},
            headers=headers,
        )
        assert r6.status_code == 200

        # 7. Containment
        r7 = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}/containment",
            params={"project_id": str(PROJECT_ID)},
            headers=headers,
        )
        assert r7.status_code == 200

        # 8. Bounded Paths
        r8 = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/paths",
            params={
                "project_id": str(PROJECT_ID),
                "source_entity_id": str(ENTITY_ID),
                "target_entity_id": str(TARGET_ENTITY_ID),
            },
            headers=headers,
        )
        assert r8.status_code == 200
    finally:
        client.close()


def test_correlation_id_handling() -> None:
    mock_query = _MockQueryService()
    app.dependency_overrides[get_graph_query_service] = lambda: mock_query

    client = TestClient(app)
    try:
        # 1. Valid custom correlation ID
        resp_valid = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params={"project_id": str(PROJECT_ID)},
            headers=_valid_headers(correlation_id="corr-trace-98765"),
        )
        assert resp_valid.status_code == 200

        # 2. Missing correlation ID (defaults to auto-generated)
        resp_missing = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params={"project_id": str(PROJECT_ID)},
            headers=_valid_headers(correlation_id=None),
        )
        assert resp_missing.status_code == 200

        # 3. Empty correlation ID (rejected as 422)
        resp_empty = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params={"project_id": str(PROJECT_ID)},
            headers=_valid_headers(correlation_id=""),
        )
        assert resp_empty.status_code == 422
        assert resp_empty.json()["error"]["code"] == "analysis_input_invalid"

        # 4. Overlong correlation ID (> 255 characters)
        resp_overlong = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/window",
            params={"project_id": str(PROJECT_ID)},
            headers=_valid_headers(correlation_id="x" * 256),
        )
        assert resp_overlong.status_code == 422
        assert resp_overlong.json()["error"]["code"] == "analysis_input_invalid"
    finally:
        client.close()


def test_rebuild_service_credential_required() -> None:
    mock_api = _MockApiService()
    app.dependency_overrides[get_graph_api_service] = lambda: mock_api

    client = TestClient(app)
    try:
        # Missing X-Service-Token
        headers = _valid_headers()
        del headers["X-Service-Token"]
        resp = client.post(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/rebuild",
            params={"project_id": str(PROJECT_ID)},
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "authentication_required"

        # Invalid X-Service-Token
        headers["X-Service-Token"] = "invalid-token"
        resp = client.post(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/rebuild",
            params={"project_id": str(PROJECT_ID)},
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_token"
        assert mock_api.call_count == 0
    finally:
        client.close()


def test_rebuild_project_mismatch_denied_before_service_invocation() -> None:
    mock_api = _MockApiService()
    app.dependency_overrides[get_graph_api_service] = lambda: mock_api

    client = TestClient(app)
    try:
        mismatched_project = uuid4()
        resp = client.post(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/rebuild",
            params={"project_id": str(mismatched_project)},
            headers=_valid_headers(project_id=PROJECT_ID, role="OWNER"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "analysis_access_denied"
        assert mock_api.call_count == 0
    finally:
        client.close()


@pytest.mark.parametrize("role", ["OWNER", "ADMIN"])
def test_rebuild_permitted_for_owner_and_admin(role: str) -> None:
    mock_api = _MockApiService()
    app.dependency_overrides[get_graph_api_service] = lambda: mock_api

    client = TestClient(app)
    try:
        resp = client.post(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/rebuild",
            params={"project_id": str(PROJECT_ID)},
            headers=_valid_headers(project_id=PROJECT_ID, role=role),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["architecture_version_id"] == str(VERSION_ID)
        assert data["status"] == "PENDING"
        assert data["attempt_status"] == "QUEUED"
        assert mock_api.call_count == 1
    finally:
        client.close()


@pytest.mark.parametrize("role", ["DEVELOPER", "VIEWER"])
def test_rebuild_denied_for_developer_and_viewer_before_lookup(role: str) -> None:
    mock_api = _MockApiService()
    app.dependency_overrides[get_graph_api_service] = lambda: mock_api

    client = TestClient(app)
    try:
        resp = client.post(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/rebuild",
            params={"project_id": str(PROJECT_ID)},
            headers=_valid_headers(project_id=PROJECT_ID, role=role),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "analysis_access_denied"
        assert mock_api.call_count == 0
    finally:
        client.close()
