"""End-to-end tests for atomic search candidate publication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AttemptIdentity,
    ExecutionControl,
    HandlerProfile,
    WorkExecutionContext,
    WorkIdentity,
    WorkKind,
    WorkSlot,
)
from backend.platform.delivery.publication import PublicationContext
from backend.platform.knowledge.elasticsearch import InMemorySearchBackend
from backend.platform.knowledge.persistence import SEARCH_TABLES
from backend.platform.knowledge.repository import (
    SearchPublicationPort,
    SqlAlchemySearchRepository,
)
from backend.platform.knowledge.service import SearchWorkHandler
from tests.p5.knowledge.conftest import make_test_profile


@pytest.fixture
def pub_env(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    profile = make_test_profile()

    engine = create_engine("sqlite:///:memory:")
    for table in SEARCH_TABLES:
        table.create(engine)
    session = Session(engine)

    backend = InMemorySearchBackend()
    repo = SqlAlchemySearchRepository(session)
    handler = SearchWorkHandler(
        backend=backend,
        repository=repo,
        document_loader=lambda s: doc,
    )
    port = SearchPublicationPort(session, backend=backend)

    binding = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.SEARCH),
        profile=profile,
    )

    yield doc, scope, profile, binding, handler, port, repo, session
    session.close()
    engine.dispose()


def test_atomic_publication_and_version_transition(pub_env):
    doc, scope, profile, binding, handler, port, repo, session = pub_env

    # 1. Attempt 1
    work1 = WorkIdentity(
        scope=scope,
        binding=binding,
        input_fingerprint="1" * 64,
        bundle_id=uuid4(),
        bundle_fingerprint="b" * 64,
        work_id=uuid4(),
        run_number=1,
    )
    attempt1 = AttemptIdentity(
        work=work1,
        attempt_id=uuid4(),
        ordinal=1,
        fence=1,
        dispatch_epoch=uuid4(),
        candidate_id=uuid4(),
    )
    control = MagicMock(spec=ExecutionControl)
    control.should_stop.return_value = False
    ctx1 = WorkExecutionContext(
        attempt=attempt1,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
        control=control,
    )

    prepared1 = handler.execute(ctx1)
    assert prepared1.candidate.sealed is True

    pub_ctx1 = PublicationContext(
        transaction_id=uuid4(),
        attempt=attempt1,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )
    accepted1 = port.publish_prepared(prepared1, pub_ctx1)
    assert accepted1.reference.candidate_id == attempt1.candidate_id
    session.commit()

    # Generation 1 is ACTIVE
    gen1 = repo.get_generation(prepared1.candidate.generation_id)
    assert gen1.state == "ACTIVE"
    active_gen = repo.get_active_generation(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    assert active_gen.generation_id == gen1.generation_id

    # 2. Attempt 2 (Successor attempt for rebuild or retry)
    attempt2 = AttemptIdentity(
        work=work1,
        attempt_id=uuid4(),
        ordinal=2,
        fence=2,
        dispatch_epoch=uuid4(),
        candidate_id=uuid4(),
    )
    ctx2 = WorkExecutionContext(
        attempt=attempt2,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
        control=control,
    )
    prepared2 = handler.execute(ctx2)

    pub_ctx2 = PublicationContext(
        transaction_id=uuid4(),
        attempt=attempt2,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )
    accepted2 = port.publish_prepared(prepared2, pub_ctx2)
    assert accepted2.reference.candidate_id == attempt2.candidate_id
    session.commit()

    # Generation 2 is ACTIVE, Generation 1 transitioned to HISTORICAL
    gen2 = repo.get_generation(prepared2.candidate.generation_id)
    assert gen2.state == "ACTIVE"
    assert gen1.state == "HISTORICAL"

    current_active = repo.get_active_generation(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    assert current_active.generation_id == gen2.generation_id


def test_publication_rollback_preserves_unactivated_candidate(pub_env):
    doc, scope, profile, binding, handler, port, repo, session = pub_env

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
    ctx = WorkExecutionContext(
        attempt=attempt,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
        control=control,
    )

    prepared = handler.execute(ctx)
    session.commit()  # Staged candidate committed as SEALED

    pub_ctx = PublicationContext(
        transaction_id=uuid4(),
        attempt=attempt,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )
    port.publish_prepared(prepared, pub_ctx)
    # Simulate transaction abort / rollback before physical WAL commit
    session.rollback()

    # Generation is still in SEALED state, NOT ACTIVE
    gen = repo.get_generation(prepared.candidate.generation_id)
    assert gen.state == "SEALED"
    active_gen = repo.get_active_generation(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    assert active_gen is None
