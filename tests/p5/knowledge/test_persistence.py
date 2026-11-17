"""Tests for P5-M2 search persistence models and table schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.platform.knowledge.persistence import (
    SEARCH_TABLES,
    SearchGenerationModel,
    SearchPublicationReceiptModel,
    SearchReadPinModel,
    SearchResourceModel,
)


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    for table in SEARCH_TABLES:
        table.create(engine)
    yield engine
    engine.dispose()


def test_search_tables_creation(sqlite_engine):
    assert len(SEARCH_TABLES) == 4
    with Session(sqlite_engine) as session:
        now = datetime.now(UTC)
        p_id = uuid4()
        v_id = uuid4()
        res = SearchResourceModel(
            id=uuid4(),
            project_id=p_id,
            architecture_version_id=v_id,
            status="PENDING",
            created_at=now,
            updated_at=now,
        )
        session.add(res)
        session.commit()

        queried = session.scalar(
            select(SearchResourceModel).where(SearchResourceModel.project_id == p_id)
        )
        assert queried is not None
        assert queried.architecture_version_id == v_id
        assert queried.status == "PENDING"


def test_search_resource_unique_constraint(sqlite_engine):
    with Session(sqlite_engine) as session:
        now = datetime.now(UTC)
        p_id = uuid4()
        v_id = uuid4()
        r1 = SearchResourceModel(
            id=uuid4(),
            project_id=p_id,
            architecture_version_id=v_id,
            status="PENDING",
            created_at=now,
            updated_at=now,
        )
        session.add(r1)
        session.commit()

        # Duplicate (project_id, architecture_version_id) rejected
        r2 = SearchResourceModel(
            id=uuid4(),
            project_id=p_id,
            architecture_version_id=v_id,
            status="PENDING",
            created_at=now,
            updated_at=now,
        )
        session.add(r2)
        with pytest.raises(IntegrityError):
            session.commit()


def test_search_generation_lifecycle_states(sqlite_engine):
    with Session(sqlite_engine) as session:
        now = datetime.now(UTC)
        p_id = uuid4()
        v_id = uuid4()
        res = SearchResourceModel(
            id=uuid4(),
            project_id=p_id,
            architecture_version_id=v_id,
            status="PENDING",
            created_at=now,
            updated_at=now,
        )
        session.add(res)
        session.commit()

        gen = SearchGenerationModel(
            generation_id=uuid4(),
            resource_id=res.id,
            project_id=p_id,
            architecture_version_id=v_id,
            candidate_id=uuid4(),
            attempt_id=uuid4(),
            artifact_id=uuid4(),
            index_name="stacksense-search-test",
            index_uuid="uuid-idx-1234",
            state="SEALED",
            counts_json={"entities": 5, "total_records": 6},
            key_set_digest="a" * 64,
            payload_digest="b" * 64,
            projection_digest="c" * 64,
            manifest_digest="d" * 64,
            sealed_at=now,
            created_at=now,
        )
        session.add(gen)
        session.commit()

        # Check retrieval
        queried = session.scalar(
            select(SearchGenerationModel).where(
                SearchGenerationModel.generation_id == gen.generation_id
            )
        )
        assert queried is not None
        assert queried.state == "SEALED"
        assert queried.counts_json["entities"] == 5


def test_search_publication_receipt_and_read_pin(sqlite_engine):
    with Session(sqlite_engine) as session:
        now = datetime.now(UTC)
        p_id = uuid4()
        v_id = uuid4()
        res = SearchResourceModel(
            id=uuid4(),
            project_id=p_id,
            architecture_version_id=v_id,
            status="PENDING",
            created_at=now,
            updated_at=now,
        )
        session.add(res)
        session.flush()

        gen_id = uuid4()
        cand_id = uuid4()
        attempt_id = uuid4()

        gen = SearchGenerationModel(
            generation_id=gen_id,
            resource_id=res.id,
            project_id=p_id,
            architecture_version_id=v_id,
            candidate_id=cand_id,
            attempt_id=attempt_id,
            artifact_id=uuid4(),
            index_name="stacksense-search-test",
            index_uuid="uuid-idx-1234",
            state="ACTIVE",
            counts_json={"entities": 1},
            key_set_digest="a" * 64,
            payload_digest="b" * 64,
            projection_digest="c" * 64,
            manifest_digest="d" * 64,
            created_at=now,
        )
        session.add(gen)
        session.flush()

        receipt = SearchPublicationReceiptModel(
            receipt_id=uuid4(),
            generation_id=gen_id,
            attempt_id=attempt_id,
            candidate_id=cand_id,
            accepted_at=now,
            artifact_reference={"binding": "search"},
        )
        session.add(receipt)

        pin = SearchReadPinModel(
            pin_id=uuid4(),
            generation_id=gen_id,
            pit_id="pit-handle-123",
            pinned_at=now,
            expires_at=now,
        )
        session.add(pin)
        session.commit()

        q_receipt = session.scalar(
            select(SearchPublicationReceiptModel).where(
                SearchPublicationReceiptModel.candidate_id == cand_id
            )
        )
        assert q_receipt is not None
        assert q_receipt.attempt_id == attempt_id

        q_pin = session.scalar(
            select(SearchReadPinModel).where(SearchReadPinModel.generation_id == gen_id)
        )
        assert q_pin is not None
        assert q_pin.pit_id == "pit-handle-123"
