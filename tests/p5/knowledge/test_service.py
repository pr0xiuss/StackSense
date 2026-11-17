"""Tests for SearchWorkHandler candidate preparation service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AttemptIdentity,
    DeliveryExecutionFailure,
    ExecutionControl,
    HandlerProfile,
    WorkExecutionContext,
    WorkIdentity,
    WorkKind,
    WorkSlot,
)
from backend.platform.knowledge.elasticsearch import InMemorySearchBackend
from backend.platform.knowledge.persistence import SEARCH_TABLES
from backend.platform.knowledge.repository import SqlAlchemySearchRepository
from backend.platform.knowledge.service import SearchWorkHandler
from tests.p5.knowledge.conftest import make_test_profile


@pytest.fixture
def service_env(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    profile = make_test_profile()

    engine = create_engine("sqlite:///:memory:")
    for table in SEARCH_TABLES:
        table.create(engine)
    session = Session(engine)

    repo = SqlAlchemySearchRepository(session)
    backend = InMemorySearchBackend()
    handler = SearchWorkHandler(
        backend=backend,
        repository=repo,
        document_loader=lambda s: doc,
    )

    binding = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.SEARCH),
        profile=profile,
    )
    work = WorkIdentity(
        scope=scope,
        binding=binding,
        input_fingerprint="1" * 64,
        bundle_id=uuid4(),
        bundle_fingerprint="b" * 64,
        work_id=uuid4(),
        run_number=1,
    )
    attempt = AttemptIdentity(
        work=work,
        attempt_id=uuid4(),
        ordinal=1,
        fence=1,
        dispatch_epoch=uuid4(),
        candidate_id=uuid4(),
    )

    control = MagicMock(spec=ExecutionControl)
    control.should_stop.return_value = False

    context = WorkExecutionContext(
        attempt=attempt,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
        control=control,
    )

    yield handler, context, repo, backend, session
    session.close()
    engine.dispose()


def test_search_work_handler_success(service_env):
    handler, context, repo, backend, session = service_env
    prepared = handler.execute(context)

    assert prepared.attempt == context.attempt
    assert prepared.candidate.sealed is True
    assert prepared.candidate.size_bytes > 0
    assert len(prepared.candidate.digests.content) == 64

    # Candidate staged in repository
    gen = repo.get_generation(prepared.candidate.generation_id)
    assert gen is not None
    assert gen.state == "SEALED"
    assert gen.candidate_id == context.attempt.candidate_id


def test_search_work_handler_cooperative_stop(service_env):
    handler, context, repo, backend, session = service_env
    context.control.should_stop.return_value = True

    with pytest.raises(DeliveryExecutionFailure) as exc_info:
        handler.execute(context)
    assert exc_info.value.failure.code == "cooperative_stop_requested"


def test_search_work_handler_source_unavailable(service_env):
    handler, context, repo, backend, session = service_env

    def fail_loader(s):
        raise RuntimeError("Disk read error")

    handler._document_loader = fail_loader

    with pytest.raises(DeliveryExecutionFailure) as exc_info:
        handler.execute(context)
    assert exc_info.value.failure.code == "source_document_unavailable"


def test_search_work_handler_bulk_failure_cleans_up(service_env):
    handler, context, repo, backend, session = service_env
    backend.simulate_failure("bulk_error")

    with pytest.raises(DeliveryExecutionFailure) as exc_info:
        handler.execute(context)
    assert exc_info.value.failure.code == "bulk_indexing_failed"


def test_search_work_handler_sealing_failure_cleans_up(service_env):
    handler, context, repo, backend, session = service_env
    backend.simulate_failure("seal_error")

    with pytest.raises(DeliveryExecutionFailure) as exc_info:
        handler.execute(context)
    assert exc_info.value.failure.code == "index_sealing_failed"
