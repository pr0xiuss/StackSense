"""Tests for P4-owned graph dependency lifecycle composition."""

from __future__ import annotations

from typing import Any

from backend.platform.config import Settings
from backend.platform.graph import dependencies


def test_neo4j_dependency_initializes_and_closes(monkeypatch: Any) -> None:
    events: list[str] = []

    class FakeInfrastructure:
        def __init__(self, settings: Settings) -> None:
            assert settings.neo4j_database == "neo4j"

        def initialize(self) -> None:
            events.append("initialize")

        def close(self) -> None:
            events.append("close")

    monkeypatch.setattr(dependencies, "Neo4jInfrastructure", FakeInfrastructure)
    provider = dependencies.get_neo4j_infrastructure(Settings())

    infrastructure = next(provider)
    assert isinstance(infrastructure, FakeInfrastructure)
    assert events == ["initialize"]

    provider.close()
    assert events == ["initialize", "close"]


def test_neo4j_dependency_accepts_unhashable_settings(monkeypatch: Any) -> None:
    class FakeInfrastructure:
        def __init__(self, settings: Settings) -> None:
            del settings

        def initialize(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(dependencies, "Neo4jInfrastructure", FakeInfrastructure)

    provider = dependencies.get_neo4j_infrastructure(Settings())
    next(provider)
    provider.close()
