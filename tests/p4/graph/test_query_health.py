"""Unit tests for M3 query capability health probe and models."""

from unittest.mock import MagicMock

from backend.platform.config import Settings
from backend.platform.graph.neo4j import (
    GraphConfigurationError,
    GraphDependencyUnavailableError,
    GraphInfrastructure,
    GraphSchemaCompatibilityError,
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

    mock_driver = MagicMock()
    mock_infra.driver = mock_driver

    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.single.return_value = {"ready": 1}
    mock_session.run.return_value = mock_result

    probe = GraphQueryHealthProbe(settings, infrastructure_factory=mock_infra_cls)
    response = probe.check()

    assert isinstance(response, GraphQueryHealthResponse)
    assert response.status == GraphQueryHealthStatus.READY
    assert response.code == "query_engine_ready"
    assert response.details is None


def test_query_health_probe_schema_incompatible() -> None:
    settings = Settings()
    mock_infra_cls = MagicMock()
    mock_infra_cls.side_effect = GraphSchemaCompatibilityError("Version mismatch")

    probe = GraphQueryHealthProbe(settings, infrastructure_factory=mock_infra_cls)
    response = probe.check()

    assert response.status == GraphQueryHealthStatus.UNAVAILABLE
    assert response.code == "graph_schema_incompatible"
    assert response.details == {"reason": "Version mismatch"}


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


def test_query_health_probe_unexpected_result() -> None:
    settings = Settings()
    mock_infra_cls = MagicMock()
    mock_infra = MagicMock(spec=GraphInfrastructure)
    mock_infra_cls.return_value = mock_infra

    mock_driver = MagicMock()
    mock_infra.driver = mock_driver

    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.single.return_value = {"ready": 0}
    mock_session.run.return_value = mock_result

    probe = GraphQueryHealthProbe(settings, infrastructure_factory=mock_infra_cls)
    response = probe.check()

    assert response.status == GraphQueryHealthStatus.DEGRADED
    assert response.code == "query_probe_unexpected_result"
