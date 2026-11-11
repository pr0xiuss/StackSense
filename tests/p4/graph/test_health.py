"""Graph health behavior and frozen core-health regression tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, literal, select
from sqlalchemy.orm import Session

from backend.api.app import app
from backend.platform.config import Settings
from backend.platform.graph.dependencies import get_graph_health_service
from backend.platform.graph.health import GraphHealthService
from backend.platform.graph.neo4j import (
    GraphConfigurationError,
    GraphDependencyUnavailableError,
    GraphInfrastructure,
    GraphSchemaCompatibilityError,
    Neo4jCapability,
)


class _InfrastructureStub:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.closed = False

    def initialize(self) -> Neo4jCapability:
        if self.failure is not None:
            raise self.failure
        return Neo4jCapability(
            server_agent="Neo4j/5.26.33",
            protocol_version="5.8",
            database="neo4j",
            graph_schema_version="1.0.0",
            constraint_names=("constraint",),
        )

    def close(self) -> None:
        self.closed = True


def _service_with_stub(stub: _InfrastructureStub) -> GraphHealthService:
    def factory(_: Settings) -> GraphInfrastructure:
        return stub

    return GraphHealthService(
        Settings(),
        infrastructure_factory=factory,
        lifecycle_ready=True,
        broker_probe=lambda: None,
    )


def test_core_health_contract_remains_exactly_unchanged() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_graph_health_reports_infrastructure_separately_from_capabilities() -> None:
    stub = _InfrastructureStub()
    app.dependency_overrides[get_graph_health_service] = lambda: _service_with_stub(
        stub
    )
    try:
        response = TestClient(app).get("/api/v1/health/graph")
    finally:
        app.dependency_overrides.pop(get_graph_health_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "components": {
            "neo4j": {"status": "ready", "code": "connected"},
            "postgresql": {
                "status": "ready",
                "code": "connected",
            },
            "rabbitmq": {"status": "ready", "code": "connected"},
        },
        "capabilities": {
            "lifecycle_persistence": "ready",
            "reconciliation_scheduling": "not_ready",
            "projection_execution": "not_ready",
        },
    }
    assert stub.closed is True


def test_graph_health_can_report_lifecycle_ready_before_execution_exists() -> None:
    stub = _InfrastructureStub()

    result = GraphHealthService(
        Settings(),
        infrastructure_factory=lambda _: stub,
        lifecycle_ready=True,
        broker_probe=lambda: None,
        scheduling_registered=True,
    ).check()

    assert result.capabilities.lifecycle_persistence == "ready"
    assert result.capabilities.reconciliation_scheduling == "ready"
    assert result.capabilities.projection_execution == "not_ready"


def test_missing_lifecycle_is_reported_without_affecting_core_health() -> None:
    stub = _InfrastructureStub()

    result = GraphHealthService(
        Settings(),
        infrastructure_factory=lambda _: stub,
        lifecycle_ready=False,
        broker_probe=lambda: None,
        scheduling_registered=True,
    ).check()

    assert result.status == "unavailable"
    assert result.components["postgresql"].code == "lifecycle_unavailable"
    assert result.capabilities.lifecycle_persistence == "not_ready"
    assert result.capabilities.reconciliation_scheduling == "not_ready"


def test_graph_health_requires_broker_and_executor_for_execution_readiness() -> None:
    stub = _InfrastructureStub()

    ready = GraphHealthService(
        Settings(),
        infrastructure_factory=lambda _: stub,
        lifecycle_ready=True,
        broker_probe=lambda: None,
        scheduling_registered=True,
        projection_execution_ready=True,
    ).check()

    def unavailable_broker() -> None:
        raise ConnectionError("secret")

    unavailable = GraphHealthService(
        Settings(),
        infrastructure_factory=lambda _: stub,
        lifecycle_ready=True,
        broker_probe=unavailable_broker,
        scheduling_registered=True,
        projection_execution_ready=True,
    ).check()

    assert ready.capabilities.projection_execution == "ready"
    assert unavailable.status == "degraded"
    assert unavailable.components["rabbitmq"].code == "dependency_unreachable"
    assert unavailable.capabilities.reconciliation_scheduling == "not_ready"
    assert unavailable.capabilities.projection_execution == "not_ready"


def test_missing_lifecycle_table_rolls_back_health_probe_transaction() -> None:
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as session:
        service = get_graph_health_service(Settings(), session)
        assert isinstance(service, GraphHealthService)
        assert session.scalar(select(literal(1))) == 1
    engine.dispose()


@pytest.mark.parametrize(
    ("failure", "expected_status", "expected_code"),
    [
        (
            GraphDependencyUnavailableError("secret-bearing upstream detail"),
            "degraded",
            "dependency_unreachable",
        ),
        (
            GraphSchemaCompatibilityError("unsafe schema detail"),
            "unavailable",
            "schema_incompatible",
        ),
        (
            GraphConfigurationError("unsafe configuration detail"),
            "unavailable",
            "configuration_invalid",
        ),
    ],
)
def test_graph_health_sanitizes_failures_and_closes_driver(
    failure: Exception,
    expected_status: str,
    expected_code: str,
) -> None:
    stub = _InfrastructureStub(failure)

    result = _service_with_stub(stub).check().model_dump(mode="json")

    assert result["status"] == expected_status
    assert result["components"]["neo4j"] == {
        "status": expected_status,
        "code": expected_code,
    }
    assert "secret" not in str(result)
    assert "unsafe" not in str(result)
    assert stub.closed is True


def test_graph_health_route_is_in_openapi() -> None:
    assert "/api/v1/health/graph" in app.openapi()["paths"]
