"""Unit tests for M3 query capability health probe and models."""

from unittest.mock import MagicMock

from backend.platform.config import Settings
from backend.platform.graph.neo4j import (
    GRAPH_SCHEMA_VERSION,
    GraphConfigurationError,
    GraphDependencyUnavailableError,
    GraphInfrastructure,
    GraphSchemaCompatibilityError,
    Neo4jCapability,
)
from backend.platform.graph.query_health import (
    GraphQueryHealthProbe,
    GraphQueryHealthResponse,
    GraphQueryHealthStatus,
)


def test_query_health_probe_ready() -> None:
    settings = Settings()
    mock_infra_cls = MagicMock()
    mock_infra = MagicMock(spec=GraphInfrastructure)
    mock_infra_cls.return_value = mock_infra

    mock_infra.initialize.return_value = Neo4jCapability(
        server_agent="Neo4j/5.26.33",
        protocol_version="5.8",
        database="neo4j",
        graph_schema_version=GRAPH_SCHEMA_VERSION,
        constraint_names=("constraint",),
        index_names=("index",),
    )

    probe = GraphQueryHealthProbe(settings, infrastructure_factory=mock_infra_cls)
    response = probe.check()

    assert isinstance(response, GraphQueryHealthResponse)
    assert response.status == GraphQueryHealthStatus.READY
    assert response.code == "query_engine_ready"
    assert response.details is None
    mock_infra.initialize.assert_called_once_with()
    mock_infra.close.assert_called_once_with()


def test_query_health_probe_schema_incompatible() -> None:
    settings = Settings()
    mock_infra_cls = MagicMock()
    mock_infra = MagicMock(spec=GraphInfrastructure)
    mock_infra_cls.return_value = mock_infra
    mock_infra.initialize.side_effect = GraphSchemaCompatibilityError(
        "Version mismatch"
    )

    probe = GraphQueryHealthProbe(settings, infrastructure_factory=mock_infra_cls)
    response = probe.check()

    assert response.status == GraphQueryHealthStatus.UNAVAILABLE
    assert response.code == "graph_schema_incompatible"
    assert response.details == {"reason": "Version mismatch"}
    mock_infra.close.assert_called_once_with()


def test_query_health_probe_configuration_invalid() -> None:
    settings = Settings()
    mock_infra_cls = MagicMock()
    mock_infra_cls.side_effect = GraphConfigurationError("Invalid URI")

    probe = GraphQueryHealthProbe(settings, infrastructure_factory=mock_infra_cls)
    response = probe.check()

    assert response.status == GraphQueryHealthStatus.UNAVAILABLE
    assert response.code == "configuration_invalid"


def test_query_health_probe_storage_unavailable() -> None:
    settings = Settings()
    mock_infra_cls = MagicMock()
    mock_infra_cls.side_effect = GraphDependencyUnavailableError("Connection refused")

    probe = GraphQueryHealthProbe(settings, infrastructure_factory=mock_infra_cls)
    response = probe.check()

    assert response.status == GraphQueryHealthStatus.UNAVAILABLE
    assert response.code == "storage_unavailable"


def test_query_health_probe_incompatible_capability_version() -> None:
    settings = Settings()
    mock_infra_cls = MagicMock()
    mock_infra = MagicMock(spec=GraphInfrastructure)
    mock_infra_cls.return_value = mock_infra

    mock_infra.initialize.return_value = Neo4jCapability(
        server_agent="Neo4j/5.26.33",
        protocol_version="5.8",
        database="neo4j",
        graph_schema_version="999.0.0",
        constraint_names=("constraint",),
        index_names=("index",),
    )

    probe = GraphQueryHealthProbe(settings, infrastructure_factory=mock_infra_cls)
    response = probe.check()

    assert response.status == GraphQueryHealthStatus.UNAVAILABLE
    assert response.code == "graph_schema_incompatible"
    mock_infra.close.assert_called_once_with()
