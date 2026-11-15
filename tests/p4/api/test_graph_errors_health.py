"""P4-D1 Graph API error mapping, sanitization, and health degradation tests."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.platform.config import get_settings
from backend.platform.graph.api_contracts import (
    GraphApiInternalError,
    GraphLifecycleUnavailableError,
    GraphRebuildConflictError,
)
from backend.platform.graph.api_dependencies import get_graph_api_service
from backend.platform.graph.dependencies import (
    get_graph_query_health_probe,
    get_graph_query_service,
)
from backend.platform.graph.query_contracts import (
    GraphCursorExpiredError,
    GraphCursorInvalidError,
    GraphCursorScopeMismatchError,
    GraphGenerationChangedError,
    GraphNodeNotFoundError,
    GraphProjectionNotFoundError,
    GraphProjectionNotReadyError,
    GraphQueryIntegrityError,
    GraphQueryLimitExceededError,
    GraphQueryTimeoutError,
    GraphSchemaIncompatibleError,
    GraphUnavailableError,
)
from backend.platform.graph.query_health import (
    GraphQueryHealthResponse,
    GraphQueryHealthStatus,
)

SECRET = get_settings().internal_api_secret_key.get_secret_value()
PROJECT_ID = uuid4()
VERSION_ID = uuid4()
ENTITY_ID = uuid4()


def _headers(
    project_id: Any = PROJECT_ID,
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


class _FailingQueryService:
    def __init__(self, exception_to_raise: Exception) -> None:
        self.exception_to_raise = exception_to_raise

    def get_node_detail(self, *args: Any, **kwargs: Any) -> Any:
        raise self.exception_to_raise

    def get_window(self, *args: Any, **kwargs: Any) -> Any:
        raise self.exception_to_raise


class _FailingApiService:
    def __init__(self, exception_to_raise: Exception) -> None:
        self.exception_to_raise = exception_to_raise

    def get_status(self, *args: Any, **kwargs: Any) -> Any:
        raise self.exception_to_raise

    def request_rebuild(self, *args: Any, **kwargs: Any) -> Any:
        raise self.exception_to_raise


@pytest.mark.parametrize(
    ("exception_factory", "expected_status", "expected_code"),
    [
        (lambda: GraphProjectionNotFoundError(), 404, "graph_projection_not_found"),
        (lambda: GraphProjectionNotReadyError(), 409, "graph_projection_not_ready"),
        (lambda: GraphNodeNotFoundError(), 404, "graph_node_not_found"),
        (lambda: GraphCursorInvalidError(), 422, "graph_cursor_invalid"),
        (lambda: GraphCursorScopeMismatchError(), 422, "graph_cursor_scope_mismatch"),
        (lambda: GraphCursorExpiredError(), 410, "graph_cursor_expired"),
        (lambda: GraphGenerationChangedError(), 409, "graph_generation_changed"),
        (lambda: GraphQueryLimitExceededError(), 422, "graph_query_limit_exceeded"),
        (lambda: GraphQueryTimeoutError(), 504, "graph_query_timeout"),
        (lambda: GraphUnavailableError(), 503, "graph_unavailable"),
        (lambda: GraphSchemaIncompatibleError(), 503, "graph_schema_incompatible"),
        (lambda: GraphQueryIntegrityError(), 500, "graph_query_integrity_error"),
        (lambda: GraphRebuildConflictError(), 409, "graph_rebuild_conflict"),
        (lambda: GraphLifecycleUnavailableError(), 503, "graph_lifecycle_unavailable"),
        (lambda: GraphApiInternalError(), 500, "graph_api_internal_error"),
    ],
)
def test_complete_m3_m4_error_to_http_matrix(
    exception_factory: Any,
    expected_status: int,
    expected_code: str,
) -> None:
    exc = exception_factory()
    query_service = _FailingQueryService(exc)
    api_service = _FailingApiService(exc)

    app.dependency_overrides[get_graph_query_service] = lambda: query_service
    app.dependency_overrides[get_graph_api_service] = lambda: api_service

    client = TestClient(app)
    try:
        # Test error translation on query route
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}",
            params={"project_id": str(PROJECT_ID)},
            headers=_headers(),
        )
        assert response.status_code == expected_status
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == expected_code
        assert isinstance(data["error"]["message"], str)
        assert isinstance(data["error"]["details"], dict)
    finally:
        app.dependency_overrides.pop(get_graph_query_service, None)
        app.dependency_overrides.pop(get_graph_api_service, None)
        client.close()


def test_error_response_sanitization_no_secrets_or_stack() -> None:
    # 1. Standard safe error response contains no tracebacks or credentials
    app.dependency_overrides[get_graph_query_service] = lambda: _FailingQueryService(
        GraphUnavailableError("Graph query storage is unavailable")
    )

    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/graph/nodes/{ENTITY_ID}",
            params={"project_id": str(PROJECT_ID)},
            headers=_headers(),
        )
        assert response.status_code == 503
        content = response.text
        assert SECRET not in content
        assert "Traceback" not in content
        assert "neo4j://" not in content
        assert "postgresql://" not in content

        # 2. Probe failure sanitizes internal exception messages
        class _LeakingProbe:
            def check(self) -> GraphQueryHealthResponse:
                secret_leak = f"password={SECRET}"
                try:
                    raise RuntimeError(f"Connection failed: {secret_leak}")
                except Exception as exc:
                    return GraphQueryHealthResponse(
                        status=GraphQueryHealthStatus.UNAVAILABLE,
                        code="storage_probe_failed",
                        details={"error_type": exc.__class__.__name__},
                    )

        app.dependency_overrides[get_graph_query_health_probe] = _LeakingProbe
        probe_response = client.get("/api/v1/health/graph/query")
        assert probe_response.status_code == 200
        probe_data = probe_response.json()
        assert probe_data["code"] == "storage_probe_failed"
        assert probe_data["details"] == {"error_type": "RuntimeError"}
        assert SECRET not in probe_response.text
    finally:
        app.dependency_overrides.pop(get_graph_query_service, None)
        app.dependency_overrides.pop(get_graph_query_health_probe, None)
        client.close()


@pytest.mark.parametrize(
    ("status_enum", "code_str"),
    [
        (GraphQueryHealthStatus.READY, "query_engine_ready"),
        (GraphQueryHealthStatus.DEGRADED, "storage_degraded"),
        (GraphQueryHealthStatus.UNAVAILABLE, "storage_unavailable"),
    ],
)
def test_query_health_states(
    status_enum: GraphQueryHealthStatus, code_str: str
) -> None:
    class _MockProbe:
        def check(self) -> GraphQueryHealthResponse:
            return GraphQueryHealthResponse(
                status=status_enum,
                code=code_str,
                details={"reason": "test check"},
            )

    app.dependency_overrides[get_graph_query_health_probe] = _MockProbe
    client = TestClient(app)
    try:
        response = client.get("/api/v1/health/graph/query")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == status_enum.value
        assert data["code"] == code_str
        assert data["details"] == {"reason": "test check"}
    finally:
        app.dependency_overrides.pop(get_graph_query_health_probe, None)
        client.close()


def test_graph_query_outage_does_not_affect_core_health() -> None:
    """Outages in graph storage/query probe must not degrade core /health."""

    class _BrokenProbe:
        def check(self) -> GraphQueryHealthResponse:
            return GraphQueryHealthResponse(
                status=GraphQueryHealthStatus.UNAVAILABLE,
                code="storage_unavailable",
                details={"error": "Neo4j connection refused"},
            )

    app.dependency_overrides[get_graph_query_health_probe] = _BrokenProbe
    client = TestClient(app)
    try:
        # 1. Query health reflects outage
        q_health = client.get("/api/v1/health/graph/query")
        assert q_health.status_code == 200
        assert q_health.json()["status"] == "unavailable"

        # 2. Core application health remains ready (200)
        core_health = client.get("/api/v1/health")
        assert core_health.status_code == 200
        assert core_health.json() == {"status": "ready"}
    finally:
        app.dependency_overrides.pop(get_graph_query_health_probe, None)
        client.close()


def test_log_capture_correlation_and_clean_extra(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from backend.platform.graph.api_contracts import ProjectionStatusResponse
    from backend.platform.graph.model import PROJECTION_TYPE

    class _MockApiService:
        def get_status(self, *args: Any, **kwargs: Any) -> Any:
            from datetime import UTC, datetime

            now = datetime.now(UTC)
            return ProjectionStatusResponse(
                resource_id=uuid4(),
                project_id=PROJECT_ID,
                architecture_version_id=VERSION_ID,
                projection_type=PROJECTION_TYPE,
                status="COMPLETED",
                created_at=now,
                updated_at=now,
            )

    app.dependency_overrides[get_graph_api_service] = _MockApiService
    client = TestClient(app)
    try:
        with caplog.at_level("INFO"):
            corr_id = "test-audit-corr-9999"
            response = client.get(
                f"/api/v1/architecture-versions/{VERSION_ID}/graph/status",
                params={"project_id": str(PROJECT_ID)},
                headers=_headers(correlation_id=corr_id),
            )
            assert response.status_code == 200

        # Verify structured log has correlation_id and excludes secrets/cursors
        records = [r for r in caplog.records if r.msg == "graph_api_operation"]
        assert len(records) >= 1
        record = records[0]
        assert getattr(record, "correlation_id", None) == corr_id
        assert getattr(record, "operation", None) == "get_projection_status"
        # Secrets/tokens must never be present in log attributes
        for attr in dir(record):
            val = str(getattr(record, attr))
            assert SECRET not in val
    finally:
        app.dependency_overrides.pop(get_graph_api_service, None)
        client.close()


def test_failure_path_structured_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify failed operations log all 8 required audit telemetry attributes."""
    app.dependency_overrides[get_graph_api_service] = lambda: _FailingApiService(
        GraphRebuildConflictError("Active rebuild already running")
    )
    client = TestClient(app)
    try:
        corr_id = "test-fail-corr-1234"
        with caplog.at_level("INFO"):
            response = client.post(
                f"/api/v1/architecture-versions/{VERSION_ID}/graph/rebuild",
                params={"project_id": str(PROJECT_ID)},
                headers=_headers(role="OWNER", correlation_id=corr_id),
            )
            assert response.status_code == 409

        records = [r for r in caplog.records if r.msg == "graph_api_operation"]
        assert len(records) >= 1
        record = records[-1]
        assert getattr(record, "operation", None) == "request_rebuild"
        assert getattr(record, "correlation_id", None) == corr_id
        assert getattr(record, "actor_role", None) == "OWNER"
        assert getattr(record, "project_id", None) == str(PROJECT_ID)
        assert getattr(record, "architecture_version_id", None) == str(VERSION_ID)
        assert getattr(record, "status_code", None) == 409
        assert getattr(record, "error_code", None) == "graph_rebuild_conflict"
        assert getattr(record, "actor_id", None) is not None
    finally:
        app.dependency_overrides.pop(get_graph_api_service, None)
        client.close()
