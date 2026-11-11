"""Real Neo4j Community and Python-driver compatibility evidence."""

import os

import pytest
from pydantic import SecretStr

from backend.platform.config import Settings
from backend.platform.graph.neo4j import (
    CONSTRAINTS,
    GraphDependencyUnavailableError,
    Neo4jInfrastructure,
)


def _integration_settings() -> Settings:
    uri = os.getenv("NEO4J_TEST_URI")
    password = os.getenv("NEO4J_TEST_PASSWORD")
    if not uri or not password:
        pytest.skip("NEO4J_TEST_URI and NEO4J_TEST_PASSWORD are required")
    return Settings(
        neo4j_uri=uri,
        neo4j_user=os.getenv("NEO4J_TEST_USER", "neo4j"),
        neo4j_password=SecretStr(password),
        neo4j_database=os.getenv("NEO4J_TEST_DATABASE", "neo4j"),
    )


def test_neo4j_community_schema_bootstrap_is_idempotent() -> None:
    settings = _integration_settings()

    with Neo4jInfrastructure(settings) as infrastructure:
        first = infrastructure.initialize()
        second = infrastructure.initialize()

    expected_names = tuple(sorted(constraint.name for constraint in CONSTRAINTS))
    assert first.server_agent.startswith("Neo4j/5.26.33")
    assert first.database == "neo4j"
    assert first.graph_schema_version == "1.0.0"
    assert first.constraint_names == expected_names
    assert second == first


def test_neo4j_authentication_failure_is_sanitized() -> None:
    settings = _integration_settings().model_copy(
        update={"neo4j_password": SecretStr("deliberately-wrong-password")}
    )

    with Neo4jInfrastructure(settings) as infrastructure:
        with pytest.raises(GraphDependencyUnavailableError) as captured:
            infrastructure.initialize()

    assert "deliberately-wrong-password" not in str(captured.value)
