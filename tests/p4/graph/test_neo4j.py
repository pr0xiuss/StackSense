"""Unit tests for Neo4j infrastructure lifecycle and schema validation."""

from collections.abc import Mapping
from typing import cast

import pytest
from neo4j import Driver

from backend.platform.config import Settings
from backend.platform.graph.neo4j import (
    CONSTRAINTS,
    GraphConfigurationError,
    GraphSchemaCompatibilityError,
    Neo4jInfrastructure,
    validate_constraint_rows,
)


def _valid_constraint_rows() -> list[Mapping[str, object]]:
    return [
        {
            "name": constraint.name,
            "type": constraint.constraint_type,
            "entityType": constraint.entity_type,
            "labelsOrTypes": [constraint.label_or_type],
            "properties": [constraint.property_name],
        }
        for constraint in CONSTRAINTS
    ]


def test_required_constraint_rows_are_accepted_deterministically() -> None:
    names = validate_constraint_rows(reversed(_valid_constraint_rows()))

    assert names == tuple(sorted(constraint.name for constraint in CONSTRAINTS))


def test_missing_constraint_fails_closed() -> None:
    with pytest.raises(GraphSchemaCompatibilityError, match="missing"):
        validate_constraint_rows(_valid_constraint_rows()[:-1])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "NODE_KEY"),
        ("entityType", "NODE"),
        ("labelsOrTypes", ["WrongLabel"]),
        ("properties", ["wrong_key"]),
    ],
)
def test_incompatible_constraint_fails_closed(field: str, value: object) -> None:
    rows = _valid_constraint_rows()
    target = dict(rows[-1])
    target[field] = value
    rows[-1] = target

    with pytest.raises(GraphSchemaCompatibilityError, match="incompatible"):
        validate_constraint_rows(rows)


class _CloseTrackingDriver:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def test_driver_close_is_idempotent() -> None:
    driver = _CloseTrackingDriver()

    def factory(*_: object, **__: object) -> Driver:
        return cast(Driver, driver)

    infrastructure = Neo4jInfrastructure(Settings(), driver_factory=factory)

    infrastructure.close()
    infrastructure.close()

    assert infrastructure.closed is True
    assert driver.close_calls == 1


@pytest.mark.parametrize(
    "uri",
    [
        "bolt://localhost:7687",
        "bolt+s://graph.internal:7687",
        "bolt+ssc://graph.internal:7687",
        "neo4j://localhost:7687",
        "neo4j+s://graph.internal:7687",
        "neo4j+ssc://graph.internal:7687",
    ],
)
def test_official_driver_accepts_supported_uri_schemes(uri: str) -> None:
    infrastructure = Neo4jInfrastructure(Settings(neo4j_uri=uri))

    infrastructure.close()

    assert infrastructure.closed is True


def test_invalid_driver_configuration_is_sanitized() -> None:
    secret = "super-sensitive-neo4j-password"

    def factory(*_: object, **__: object) -> Driver:
        raise ValueError(f"bad password: {secret}")

    with pytest.raises(GraphConfigurationError) as captured:
        Neo4jInfrastructure(
            Settings(neo4j_password=secret),
            driver_factory=factory,
        )

    assert secret not in str(captured.value)
