"""P4-S1 published Architecture Version adapter tests."""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.persistence import ArchitectureVersionModel
from backend.platform.graph.source import SqlAlchemyPublishedArchitectureSource
from backend.platform.projects.infra.base import Base


def _version(
    value: int,
    *,
    state: str = "published",
) -> ArchitectureVersionModel:
    now = datetime.now(UTC)
    return ArchitectureVersionModel(
        id=UUID(int=value),
        analysis_id=uuid4(),
        project_id=UUID(int=1),
        repository_id=UUID(int=2),
        snapshot_id=uuid4(),
        sequence_number=value,
        state=state,
        configuration_fingerprint="configuration",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        content_digest=f"digest-{value}",
        completeness={},
        source_diagnostic_ids=[],
        entity_count=value,
        relationship_count=1,
        evidence_count=2,
        unresolved_relationship_count=0,
        conflict_count=0,
        diagnostic_id=None,
        failure_code=None,
        created_at=now,
        updated_at=now,
        published_at=now if state == "published" else None,
    )


def test_source_pages_are_complete_deterministic_and_published_only() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all((_version(1), _version(2), _version(4, state="building")))
        session.flush()
        source = SqlAlchemyPublishedArchitectureSource(session)

        first = source.list_published(limit=1)
        assert [item.sequence_number for item in first.items] == [1]
        assert first.next_cursor is not None
        session.add(_version(3))
        session.flush()
        second = source.list_published(limit=5, after=first.next_cursor)
        assert [item.sequence_number for item in second.items] == [2, 3]
        assert second.next_cursor is None
        assert first.items[0].counts.entities == 1
    engine.dispose()


def test_exact_load_delegates_to_frozen_p3_loader() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    version_id = uuid4()
    project_id = uuid4()
    sentinel = object()
    with (
        Session(engine) as session,
        patch(
            "backend.platform.graph.source.SqlAlchemyArchitectureRepository.load_published_document",
            return_value=sentinel,
        ) as loader,
    ):
        result = SqlAlchemyPublishedArchitectureSource(session).load_exact(
            version_id, project_id
        )
    assert result is sentinel
    loader.assert_called_once_with(version_id, project_id)
    engine.dispose()
