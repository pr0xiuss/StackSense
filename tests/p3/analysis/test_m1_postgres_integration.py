"""Real PostgreSQL verification for M1 persistence and concurrency semantics."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from backend.platform.analysis.domain.analysis import Analysis, AnalysisConfiguration
from backend.platform.analysis.domain.constants import AnalysisStatus
from backend.platform.analysis.infra.analysis_repository import (
    SqlAlchemyAnalysisRepository,
)
from backend.platform.analysis.infra.lifecycle_model import AnalysisModel
from backend.platform.dependency_injection import get_database_settings
from backend.platform.errors import AnalysisStateConflictError


def _database_url() -> str:
    url = os.getenv("STACKSENSE_TEST_DATABASE_URL") or (
        get_database_settings().database_url.get_secret_value()
    )
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _analysis() -> Analysis:
    now = datetime.now(UTC)
    return Analysis(
        id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        status=AnalysisStatus.CREATED,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )


def test_postgres_accepts_opaque_platform_ids_and_enforces_idempotency() -> None:
    engine = create_engine(_database_url())
    analysis = _analysis()
    try:
        with Session(engine) as session:
            repository = SqlAlchemyAnalysisRepository(session)
            repository.save(analysis, idempotency_key="postgres-contract")
            session.commit()

        with Session(engine) as session:
            repository = SqlAlchemyAnalysisRepository(session)
            replay = repository.save(analysis, idempotency_key="postgres-contract")
            assert replay.id == analysis.id
            assert repository.get_by_id(analysis.id, analysis.project_id) is not None
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(AnalysisModel).where(AnalysisModel.id == analysis.id)
            )
        engine.dispose()


def test_postgres_optimistic_update_rejects_stale_writer() -> None:
    engine = create_engine(_database_url())
    analysis = _analysis()
    try:
        with Session(engine) as setup:
            SqlAlchemyAnalysisRepository(setup).save(analysis)
            setup.commit()

        with Session(engine) as first, Session(engine) as second:
            first_repo = SqlAlchemyAnalysisRepository(first)
            second_repo = SqlAlchemyAnalysisRepository(second)
            first_copy = first_repo.get_by_id(analysis.id, analysis.project_id)
            second_copy = second_repo.get_by_id(analysis.id, analysis.project_id)
            assert first_copy is not None and second_copy is not None

            first_repo.update(
                first_copy.transition_to(
                    AnalysisStatus.QUEUED, updated_at=datetime.now(UTC)
                ),
                expected_version=1,
            )
            first.commit()

            with pytest.raises(AnalysisStateConflictError):
                second_repo.update(
                    second_copy.transition_to(
                        AnalysisStatus.FAILED, updated_at=datetime.now(UTC)
                    ),
                    expected_version=1,
                )
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(AnalysisModel).where(AnalysisModel.id == analysis.id)
            )
        engine.dispose()
