"""Real Neo4j Community and Python-driver compatibility evidence."""

import os

import pytest
from neo4j import GraphDatabase
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

    with GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    ) as driver:
        with driver.session(database=settings.neo4j_database) as session:
            legacy_count = session.run(
                "MATCH (manifest:ArchitectureProjectionGeneration) "
                "RETURN count(manifest) AS count"
            ).single(strict=True)
            node_count = session.run("MATCH (node) RETURN count(node) AS count").single(
                strict=True
            )
            relationship_count = session.run(
                "MATCH ()-[relationship]->() RETURN count(relationship) AS count"
            ).single(strict=True)
            assert legacy_count is not None
            assert node_count is not None
            assert relationship_count is not None
            assert legacy_count["count"] == 0
            assert node_count["count"] == 0
            assert relationship_count["count"] == 0
            session.run(
                "DROP CONSTRAINT projection_manifest_generation_key_unique IF EXISTS"
            ).consume()
            session.run(
                "CREATE CONSTRAINT "
                "architecture_projection_generation_key_unique IF NOT EXISTS "
                "FOR (manifest:ArchitectureProjectionGeneration) "
                "REQUIRE manifest.generation_key IS UNIQUE"
            ).consume()

    with Neo4jInfrastructure(settings) as infrastructure:
        first = infrastructure.initialize()
        second = infrastructure.initialize()

    expected_names = tuple(sorted(constraint.name for constraint in CONSTRAINTS))
    assert first.server_agent.startswith("Neo4j/5.26.33")
    assert first.database == "neo4j"
    assert first.graph_schema_version == "1.0.0"
    assert first.constraint_names == expected_names
    assert second == first

    with GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    ) as driver:
        with driver.session(database=settings.neo4j_database) as session:
            rows = session.run(
                "SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties "
                "WHERE name IN $names "
                "RETURN name, labelsOrTypes, properties ORDER BY name",
                names=[
                    "architecture_projection_generation_key_unique",
                    "projection_manifest_generation_key_unique",
                ],
            ).data()
    assert rows == [
        {
            "name": "projection_manifest_generation_key_unique",
            "labelsOrTypes": ["ProjectionManifest"],
            "properties": ["generation_key"],
        }
    ]


def test_neo4j_authentication_failure_is_sanitized() -> None:
    settings = _integration_settings().model_copy(
        update={"neo4j_password": SecretStr("deliberately-wrong-password")}
    )

    with Neo4jInfrastructure(settings) as infrastructure:
        with pytest.raises(GraphDependencyUnavailableError) as captured:
            infrastructure.initialize()

    assert "deliberately-wrong-password" not in str(captured.value)
