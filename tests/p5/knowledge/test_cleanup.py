"""Tests for SearchCleanupService safe orphan index deletion and protections."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.knowledge.elasticsearch import InMemorySearchBackend
from backend.platform.knowledge.persistence import SEARCH_TABLES
from backend.platform.knowledge.repository import SqlAlchemySearchRepository
from backend.platform.knowledge.service import SearchCleanupService
from tests.p5.knowledge.conftest import (
    make_test_profile,
    make_test_scope,
)
from tests.p5.knowledge.test_reader import stage_and_publish_test_index
from tests.p5.knowledge.test_repository import make_dummy_manifest


@pytest.fixture
def cleanup_env():
    engine = create_engine("sqlite:///:memory:")
    for table in SEARCH_TABLES:
        table.create(engine)
    session = Session(engine)

    backend = InMemorySearchBackend()
    repo = SqlAlchemySearchRepository(session)
    service = SearchCleanupService(repo, backend, session)

    yield service, backend, repo, session
    session.close()
    engine.dispose()


def test_cleanup_mark_is_not_retirement_or_deletion_authority(cleanup_env):
    service, backend, repo, session = cleanup_env
    scope = make_test_scope()
    profile = make_test_profile()

    resource = repo.ensure_resource(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    gen_id = uuid4()
    idx_name = f"orphan-index-{gen_id.hex[:8]}"
    backend.create_index(idx_name, {}, {})

    manifest = make_dummy_manifest(scope, profile, uuid4(), gen_id)
    repo.stage_candidate(
        resource_id=resource.id,
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        candidate_id=manifest.candidate_id,
        attempt_id=uuid4(),
        artifact_id=manifest.artifact_id,
        generation_id=gen_id,
        index_name=idx_name,
        index_uuid="uuid-1",
        counts=manifest.counts,
        manifest=manifest,
    )
    # Mark generation for cleanup
    repo.mark_cleanup(gen_id)
    session.commit()

    assert backend.is_healthy()
    assert idx_name in backend._indexes

    deleted = service.cleanup_orphans(older_than_seconds=0.0)
    assert deleted == 0
    assert idx_name in backend._indexes
    assert repo.get_generation(gen_id) is not None


def test_cleanup_protects_active_generation(cleanup_env):
    service, backend, repo, session = cleanup_env
    scope = make_test_scope()

    _, gen_id, idx_name = stage_and_publish_test_index(
        repo, backend, session, scope, []
    )

    deleted = service.cleanup_orphans(older_than_seconds=0.0)
    assert deleted == 0
    assert idx_name in backend._indexes
    assert repo.get_generation(gen_id) is not None


def test_cleanup_protects_historical_generation(cleanup_env):
    service, backend, repo, session = cleanup_env
    scope = make_test_scope()

    _, gen_id, idx_name = stage_and_publish_test_index(
        repo, backend, session, scope, []
    )

    gen = repo.get_generation(gen_id)
    assert gen is not None
    gen.state = "HISTORICAL"
    session.commit()

    deleted = service.cleanup_orphans(older_than_seconds=0.0)
    assert deleted == 0
    assert idx_name in backend._indexes


def test_cleanup_protects_generation_with_active_read_pin(cleanup_env):
    service, backend, repo, session = cleanup_env
    scope = make_test_scope()
    profile = make_test_profile()

    resource = repo.ensure_resource(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    gen_id = uuid4()
    idx_name = f"pinned-index-{gen_id.hex[:8]}"
    backend.create_index(idx_name, {}, {})

    manifest = make_dummy_manifest(scope, profile, uuid4(), gen_id)
    repo.stage_candidate(
        resource_id=resource.id,
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        candidate_id=manifest.candidate_id,
        attempt_id=uuid4(),
        artifact_id=manifest.artifact_id,
        generation_id=gen_id,
        index_name=idx_name,
        index_uuid="uuid-1",
        counts=manifest.counts,
        manifest=manifest,
    )
    repo.mark_cleanup(gen_id)

    # Acquire an active read pin
    repo.acquire_read_pin(generation_id=gen_id, ttl_seconds=300.0)
    session.commit()

    # Cleanup should skip this pinned generation
    deleted = service.cleanup_orphans(older_than_seconds=0.0)
    assert deleted == 0
    assert idx_name in backend._indexes
    assert repo.get_generation(gen_id) is not None
