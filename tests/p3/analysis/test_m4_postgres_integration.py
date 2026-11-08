"""Real PostgreSQL verification for M4 publication and concurrency semantics."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.persistence import (
    ArchitectureEntityModel,
    ArchitectureVersionModel,
    SqlAlchemyArchitectureRepository,
)
from backend.platform.analysis.architecture.repository import ArchitectureVersionState
from backend.platform.analysis.architecture.service import (
    ArchitecturePublicationService,
)
from backend.platform.analysis.architecture.validator import (
    ArchitectureCapacityConfig,
    ArchitectureValidator,
)
from backend.platform.analysis.infra.analysis_repository import (
    SqlAlchemyAnalysisRepository,
)
from backend.platform.analysis.infra.lifecycle_model import AnalysisModel
from backend.platform.dependency_injection import get_database_settings
from tests.p3.analysis.test_m4_persistence import _analysis, _document, _validated


def _database_url() -> str:
    url = os.getenv("STACKSENSE_TEST_DATABASE_URL") or (
        get_database_settings().database_url.get_secret_value()
    )
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def test_postgres_concurrent_reservation_and_publication_are_idempotent() -> None:
    engine = create_engine(_database_url())
    document = _document()
    with Session(engine) as setup:
        _analysis(setup, document)

    reserve_barrier = Barrier(2)

    def reserve() -> tuple[str, int]:
        with Session(engine) as session:
            repository = SqlAlchemyArchitectureRepository(session)
            service = ArchitecturePublicationService(
                repository,
                validator=ArchitectureValidator(ArchitectureCapacityConfig()),
                publication_linker=SqlAlchemyAnalysisRepository(session),
                checkpoint=session.commit,
                rollback=session.rollback,
            )
            reserve_barrier.wait()
            record = service.reserve_candidate(document)
            return str(record.id), record.sequence_number

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            reservations = list(executor.map(lambda _: reserve(), range(2)))
        assert reservations == [
            (str(document.architecture_version_id), 1),
            (str(document.architecture_version_id), 1),
        ]

        with Session(engine) as session:
            repository = SqlAlchemyArchitectureRepository(session)
            ArchitecturePublicationService(
                repository,
                validator=ArchitectureValidator(ArchitectureCapacityConfig()),
                publication_linker=SqlAlchemyAnalysisRepository(session),
                checkpoint=session.commit,
                rollback=session.rollback,
            ).begin_validation(document.architecture_version_id, document.analysis_id)

        publish_barrier = Barrier(2)

        def publish() -> ArchitectureVersionState:
            with Session(engine) as session:
                repository = SqlAlchemyArchitectureRepository(session)
                service = ArchitecturePublicationService(
                    repository,
                    validator=ArchitectureValidator(ArchitectureCapacityConfig()),
                    publication_linker=SqlAlchemyAnalysisRepository(session),
                    checkpoint=session.commit,
                    rollback=session.rollback,
                )
                publish_barrier.wait()
                return service.publish(_validated(document)).state

        with ThreadPoolExecutor(max_workers=2) as executor:
            states = list(executor.map(lambda _: publish(), range(2)))
        assert states == [
            ArchitectureVersionState.PUBLISHED,
            ArchitectureVersionState.PUBLISHED,
        ]

        with Session(engine) as verification:
            assert (
                verification.scalar(
                    select(func.count())
                    .select_from(ArchitectureVersionModel)
                    .where(ArchitectureVersionModel.analysis_id == document.analysis_id)
                )
                == 1
            )
            assert verification.scalar(
                select(func.count())
                .select_from(ArchitectureEntityModel)
                .where(
                    ArchitectureEntityModel.version_id
                    == document.architecture_version_id
                )
            ) == len(document.entities)
            restored = SqlAlchemyArchitectureRepository(
                verification
            ).load_published_document(
                document.architecture_version_id, document.project_id
            )
            assert restored is not None
            assert restored.content_digest == document.content_digest
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(AnalysisModel).where(AnalysisModel.id == document.analysis_id)
            )
        engine.dispose()
