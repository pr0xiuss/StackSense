"""Tests for report failure recovery, pins, and operator deletion reservations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AttemptIdentity,
    AttemptRetirement,
    AttemptRetirementReader,
)
from backend.platform.reports.persistence import (
    REPORT_TABLES,
)
from backend.platform.reports.repository import ReportRepository
from tests.p5.reports.conftest import sample_work_context


class FakeRetirementReader(AttemptRetirementReader):
    def __init__(self, retired_attempts: set[UUID]) -> None:
        self.retired_attempts = retired_attempts

    def read_retirement(self, attempt: AttemptIdentity) -> AttemptRetirement | None:
        if attempt.attempt_id in self.retired_attempts:
            return AttemptRetirement(
                attempt=attempt,
                outcome="FAILED",
                ended_at=datetime.now(UTC),
                publication=None,
            )
        return None


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    for table in REPORT_TABLES:
        table.create(engine, checkfirst=True)
    yield engine
    engine.dispose()


def test_read_pin_lifecycle_and_deletion_guard(memory_db) -> None:
    context, diagrams = sample_work_context()
    candidate_id = uuid4()
    artifact_id = uuid4()

    with Session(memory_db) as session:
        repo = ReportRepository(session)
        gen = repo.allocate_candidate(context.attempt, candidate_id, artifact_id)
        # Mock transition to ACCEPTED directly for pin testing
        gen.state = "ACCEPTED"
        session.commit()

        # 1. Acquire read pin
        actor_id = uuid4()
        pin = repo.acquire_pin(candidate_id, actor_id=actor_id, purpose="download")
        session.commit()
        assert pin.generation_id == candidate_id
        assert pin.purpose == "download"

        # 2. Attempt deletion reservation while pinned: must be rejected
        reader = FakeRetirementReader({context.attempt.attempt_id})
        reserved = repo.reserve_for_deletion(
            candidate_id, actor_id=actor_id, retirement_reader=reader
        )
        assert reserved is False

        # 3. Release pin
        repo.release_pin(pin.id)
        session.commit()

        # 4. Now deletion reservation on unaccepted or non-accepted:
        # Note: accepted generations cannot be deleted in v1!
        # If gen is STAGING or INVALID and retired, it can be reserved.
        gen.state = "STAGING"
        session.commit()
        reserved_staging = repo.reserve_for_deletion(
            candidate_id, actor_id=actor_id, retirement_reader=reader
        )
        session.commit()
        assert reserved_staging is True
        assert gen.state == "DELETING"
        assert gen.deletion_nonce is not None


def test_reserve_deletion_requires_retired_attempt(memory_db) -> None:
    context, diagrams = sample_work_context()
    candidate_id = uuid4()
    artifact_id = uuid4()

    with Session(memory_db) as session:
        repo = ReportRepository(session)
        gen = repo.allocate_candidate(context.attempt, candidate_id, artifact_id)
        session.commit()

        actor_id = uuid4()
        # Attempt not in retired set
        reader = FakeRetirementReader(set())
        reserved = repo.reserve_for_deletion(
            candidate_id, actor_id=actor_id, retirement_reader=reader
        )
        assert reserved is False
        assert gen.state == "STAGING"
