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
    service = SearchStatusService(repo, backend=backend)

    yield service, backend, repo, session
    session.close()
    engine.dispose()


def test_status_resource_not_found(status_env):
    service, backend, repo, session = status_env
    scope = make_test_scope()
    service._scope_reader = lambda p, v: scope

    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.resource_state == "PENDING"
    assert status.freshness == "UNAVAILABLE"
    assert status.is_readable is False
    assert status.capabilities.lexical == CapabilityState.AVAILABLE
    assert status.capabilities.semantic == CapabilityState.UNAVAILABLE
    assert status.capabilities.hybrid == CapabilityState.UNAVAILABLE


def test_status_rejects_foreign_authoritative_scope(status_env):
    from backend.platform.knowledge.contracts import SearchIntegrityError

    service, _, _, _ = status_env
    requested, foreign = make_test_scope(), make_test_scope()
    service._scope_reader = lambda p, v: foreign
    with pytest.raises(SearchIntegrityError):
        service.get_status(requested.project_id, requested.architecture_version_id)


def test_status_corrupt_receipt_is_typed_integrity_failure(status_env):
    from backend.platform.knowledge.contracts import SearchIntegrityError

    service, backend, repo, session = status_env
    scope = make_test_scope()
    service._scope_reader = lambda p, v: scope
    _, generation, _ = stage_and_publish_test_index(repo, backend, session, scope, [])
    receipt = repo.get_publication_receipt(generation)
    receipt.artifact_reference = {"malformed": True}
    session.commit()
    with pytest.raises(SearchIntegrityError):
        service.get_status(scope.project_id, scope.architecture_version_id)


@pytest.mark.parametrize(
    "current,expected", [(True, "CURRENT"), (False, "STALE"), (None, "UNKNOWN")]
)
def test_freshness_requires_authoritative_observation(status_env, current, expected):
    service, backend, repo, session = status_env
    scope = make_test_scope()
    service._scope_reader = lambda p, v: scope
    service._current_version_reader = lambda _: current
    stage_and_publish_test_index(repo, backend, session, scope, [])
    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.freshness == expected
    assert status.is_current_version is current


def test_m1_running_successor_does_not_hide_old_readable_generation(status_env):
    from backend.platform.delivery.api_contracts import WorkSummary
    from backend.platform.delivery.contracts import WorkKind

    service, backend, repo, session = status_env
    scope = make_test_scope()
    service._scope_reader = lambda p, v: scope
    service._current_version_reader = lambda _: True
    service._work_reader = lambda _: WorkSummary(kind=WorkKind.SEARCH, state="RUNNING")
    stage_and_publish_test_index(repo, backend, session, scope, [])
    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.is_readable and status.active_reference is not None
    assert status.freshness == "BUILDING"
    assert status.attempt_state == "RUNNING"
    assert status.resource_state == "COMPLETED"


@pytest.mark.parametrize(
    "current,expected", [(True, "CURRENT"), (False, "STALE"), (None, "UNKNOWN")]
)
def test_failed_rebuild_preserves_accepted_resource(status_env, current, expected):
    from backend.platform.delivery.api_contracts import WorkSummary
    from backend.platform.delivery.contracts import WorkKind

    service, backend, repo, session = status_env
    scope = make_test_scope()
    service._scope_reader = lambda p, v: scope
    service._current_version_reader = lambda _: current
    service._work_reader = lambda _: WorkSummary(
        kind=WorkKind.SEARCH, state="FAILED", reason="fixture_failure"
    )
    stage_and_publish_test_index(repo, backend, session, scope, [])
    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.is_readable and status.active_reference is not None
    assert status.resource_state == ("STALE" if current is False else "COMPLETED")
    assert status.freshness == expected
    assert status.last_failure_code == "fixture_failure"
    assert status.attempt_state == "FAILED"


def test_status_building_state(status_env):
    service, backend, repo, session = status_env
    scope = make_test_scope()
    service._scope_reader = lambda p, v: scope

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
    service._scope_reader = lambda p, v: scope

    res_id, gen_id, _ = stage_and_publish_test_index(repo, backend, session, scope, [])

    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.resource_state == "COMPLETED"
    assert status.freshness == "UNKNOWN"
    assert status.is_readable is True
    assert status.is_current_version is None
    assert status.active_reference is not None
    assert status.active_reference.generation_id == gen_id


def test_status_historical_stale_generation(status_env):
    service, backend, repo, session = status_env
    scope = make_test_scope()
    service._scope_reader = lambda p, v: scope

    # Publish generation 1
    _, gen_id_1, _ = stage_and_publish_test_index(repo, backend, session, scope, [])

    # Transition generation 1 to HISTORICAL
    gen1 = repo.get_generation(gen_id_1)
    assert gen1 is not None
    gen1.state = "HISTORICAL"
    session.commit()

    status = service.get_status(scope.project_id, scope.architecture_version_id)
    assert status.resource_state == "COMPLETED"
    assert status.freshness == "UNKNOWN"
    assert status.is_readable is True
    assert status.is_current_version is None
