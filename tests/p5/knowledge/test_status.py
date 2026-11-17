"""Tests for SearchStatusService freshness, readiness, and capabilities reporting."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.knowledge.contracts import CapabilityState
from backend.platform.knowledge.elasticsearch import InMemorySearchBackend
from backend.platform.knowledge.persistence import SEARCH_TABLES
from backend.platform.knowledge.repository import SqlAlchemySearchRepository
from backend.platform.knowledge.service import SearchStatusService
from tests.p5.knowledge.conftest import make_test_scope
from tests.p5.knowledge.test_reader import stage_and_publish_test_index


@pytest.fixture
def status_env():
    engine = create_engine("sqlite:///:memory:")
    for table in SEARCH_TABLES:
        table.create(engine)
    session = Session(engine)

    backend = InMemorySearchBackend()
    repo = SqlAlchemySearchRepository(session)
    service = SearchStatusService(repo)

    yield service, backend, repo, session
    session.close()
    engine.dispose()


def test_status_resource_not_found(status_env):
    service, backend, repo, session = status_env
    scope = make_test_scope()

    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.resource_state == "PENDING"
    assert status.freshness == "UNAVAILABLE"
    assert status.is_readable is False
    assert status.capabilities.lexical == CapabilityState.AVAILABLE
    assert status.capabilities.semantic == CapabilityState.UNAVAILABLE
    assert status.capabilities.hybrid == CapabilityState.UNAVAILABLE


def test_status_building_state(status_env):
    service, backend, repo, session = status_env
    scope = make_test_scope()

    # Create resource in PENDING state with no active generation
    repo.ensure_resource(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    session.commit()

    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.resource_state == "PENDING"
    assert status.freshness == "BUILDING"
    assert status.is_readable is False


def test_status_active_current_generation(status_env):
    service, backend, repo, session = status_env
    scope = make_test_scope()

    res_id, gen_id, _ = stage_and_publish_test_index(repo, backend, session, scope, [])

    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.resource_state == "READY"
    assert status.freshness == "CURRENT"
    assert status.is_readable is True
    assert status.is_current_version is True
    assert status.active_reference is not None
    assert status.active_reference.generation_id == gen_id


def test_status_historical_stale_generation(status_env):
    service, backend, repo, session = status_env
    scope = make_test_scope()

    # Publish generation 1
    _, gen_id_1, _ = stage_and_publish_test_index(repo, backend, session, scope, [])

    # Transition generation 1 to HISTORICAL
    gen1 = repo.get_generation(gen_id_1)
    assert gen1 is not None
    gen1.state = "HISTORICAL"
    session.commit()

    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.resource_state == "READY"
    assert status.freshness == "STALE"
    assert status.is_readable is True
    assert status.is_current_version is False
