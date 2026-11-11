"""Configuration tests for P4 graph infrastructure."""

import pytest
from pydantic import SecretStr, ValidationError

from backend.platform.config import Settings


def test_graph_configuration_accepts_supported_uri_and_masks_secret() -> None:
    settings = Settings(
        neo4j_uri="neo4j+ssc://graph.internal:7687",
        neo4j_password=SecretStr("a-secure-graph-password"),
    )

    assert settings.neo4j_uri == "neo4j+ssc://graph.internal:7687"
    assert settings.neo4j_password.get_secret_value() == "a-secure-graph-password"
    assert "a-secure-graph-password" not in repr(settings)
    assert "a-secure-graph-password" not in str(settings)


@pytest.mark.parametrize(
    "uri",
    [
        "http://localhost:7474",
        "bolt://neo4j:password@localhost:7687",
        "bolt://",
    ],
)
def test_graph_configuration_rejects_unsafe_or_invalid_uri(uri: str) -> None:
    with pytest.raises(ValidationError):
        Settings(neo4j_uri=uri)


def test_graph_configuration_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        Settings(neo4j_password=SecretStr("short"))


def test_default_graph_secret_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="NEO4J_PASSWORD"):
        Settings(
            app_env="production",
            internal_api_secret_key=SecretStr("production-internal-api-secret"),
            platform_api_secret_key=SecretStr("production-platform-api-secret"),
        )


def test_changed_graph_secret_is_accepted_in_production() -> None:
    settings = Settings(
        app_env="production",
        internal_api_secret_key=SecretStr("production-internal-api-secret"),
        platform_api_secret_key=SecretStr("production-platform-api-secret"),
        neo4j_password=SecretStr("production-neo4j-secret"),
    )

    assert settings.app_env == "production"


def test_graph_scheduling_defaults_fail_closed() -> None:
    settings = Settings()

    assert settings.graph_queue_name == "graph.projections"
    assert settings.graph_maintenance_queue_name == "graph.maintenance"
    assert settings.graph_projection_dispatch_enabled is False
    assert (
        settings.graph_heartbeat_interval_seconds
        < settings.graph_lease_duration_seconds
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"graph_queue_name": "  "},
        {"graph_maintenance_queue_name": "  "},
        {"graph_maintenance_queue_name": "graph.projections"},
        {
            "graph_heartbeat_interval_seconds": 30,
            "graph_capability_ttl_seconds": 30,
        },
        {
            "graph_heartbeat_interval_seconds": 120,
            "graph_lease_duration_seconds": 120,
        },
    ],
)
def test_graph_scheduling_rejects_invalid_operational_settings(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)
