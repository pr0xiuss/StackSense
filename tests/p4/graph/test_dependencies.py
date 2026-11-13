"""Tests for P4-owned graph dependency lifecycle composition."""

from __future__ import annotations

from typing import Any

from backend.platform.config import Settings
from backend.platform.graph import dependencies
from backend.platform.graph.query_health import GraphQueryHealthProbe
from backend.platform.graph.query_repository import (
    FakeGraphGenerationReader,
    FakeGraphQueryRepository,
    Neo4jGraphQueryRepository,
    SqlAlchemyGraphGenerationReader,
)
from backend.platform.graph.query_service import GraphQueryService


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


def test_query_generation_reader_dependency() -> None:
    session = None  # type: ignore[arg-type]
    reader = dependencies.get_graph_generation_reader(session)
    assert isinstance(reader, SqlAlchemyGraphGenerationReader)


def test_query_repository_dependency() -> None:
    class FakeDriver:
        pass

    class FakeInfra:
        driver = FakeDriver()  # type: ignore[assignment]

    settings = Settings()
    repo = dependencies.get_graph_query_repository(settings, FakeInfra())  # type: ignore[arg-type]
    assert isinstance(repo, Neo4jGraphQueryRepository)


def test_query_service_dependency() -> None:
    settings = Settings()
    reader = FakeGraphGenerationReader()
    repo = FakeGraphQueryRepository()
    svc = dependencies.get_graph_query_service(settings, reader, repo)
    assert isinstance(svc, GraphQueryService)


def test_query_health_probe_dependency() -> None:
    settings = Settings()
    probe = dependencies.get_graph_query_health_probe(settings)
    assert isinstance(probe, GraphQueryHealthProbe)
