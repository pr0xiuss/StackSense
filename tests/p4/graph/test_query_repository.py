"""Unit tests for M3 generation reader and repository adapters."""

import time
from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTION_TYPE,
    PROJECTOR_VERSION,
    ProjectionCounts,
    ProjectionPublicState,
)
from backend.platform.graph.persistence import (
    GraphProjectionResourceModel,
)
from backend.platform.graph.query_contracts import (
    GraphProjectionNotFoundError,
    GraphProjectionNotReadyError,
    GraphQueryIntegrityError,
    GraphQueryTimeoutError,
    GraphReadScope,
)
from backend.platform.graph.query_repository import (
    FakeGraphGenerationReader,
    Neo4jGraphQueryRepository,
    SqlAlchemyGraphGenerationReader,
)


@pytest.fixture
def db_session() -> Generator[Session]:
    engine = create_engine("sqlite:///:memory:")
    GraphProjectionResourceModel.__table__.create(engine)  # type: ignore[attr-defined]
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _create_resource(
    session: Session,
    *,
    project_id: UUID | None = None,
    architecture_version_id: UUID | None = None,
    state: str = ProjectionPublicState.COMPLETED.value,
    active_generation_id: UUID | None = None,
) -> GraphProjectionResourceModel:
    now = datetime.now(UTC)
    is_active = state in ("COMPLETED", "STALE")
    gen_id = active_generation_id if is_active else None

    resource = GraphProjectionResourceModel(
        id=uuid4(),
        architecture_version_id=architecture_version_id or uuid4(),
        project_id=project_id or uuid4(),
        repository_id=uuid4(),
        architecture_sequence=1,
        projection_type=PROJECTION_TYPE,
        source_content_digest="source-digest",
        source_schema_version="1.0.0",
        state=state,
        active_generation_id=gen_id or (uuid4() if is_active else None),
        active_projector_version=PROJECTOR_VERSION if is_active else None,
        active_graph_schema_version=GRAPH_SCHEMA_VERSION if is_active else None,
        active_payload_digest="payload-digest" if is_active else None,
        active_entity_count=15 if is_active else None,
        active_relationship_count=25 if is_active else None,
        active_evidence_count=35 if is_active else None,
        active_unresolved_count=0 if is_active else None,
        active_conflict_count=0 if is_active else None,
        last_failure_code=None,
        last_failure_message=None,
        version=1,
        created_at=now,
        updated_at=now,
        activated_at=now if is_active else None,
    )
    session.add(resource)
    session.commit()
    return resource


def test_resolve_active_generation_completed(db_session: Session) -> None:
    resource = _create_resource(db_session, state="COMPLETED")
    reader = SqlAlchemyGraphGenerationReader(db_session)

    scope = reader.resolve_active_generation(
        project_id=resource.project_id,
        architecture_version_id=resource.architecture_version_id,
    )

    assert scope.project_id == resource.project_id
    assert scope.architecture_version_id == resource.architecture_version_id
    assert scope.generation_id == resource.active_generation_id
    assert scope.resource_state == "COMPLETED"
    assert scope.graph_schema_version == GRAPH_SCHEMA_VERSION
    assert scope.projector_version == PROJECTOR_VERSION
    assert scope.counts.entities == 15
    assert scope.counts.relationships == 25
    assert scope.counts.evidence == 35


def test_resolve_active_generation_stale_accepted(db_session: Session) -> None:
    resource = _create_resource(db_session, state="STALE")
    reader = SqlAlchemyGraphGenerationReader(db_session)

    scope = reader.resolve_active_generation(
        project_id=resource.project_id,
        architecture_version_id=resource.architecture_version_id,
    )
    assert scope.resource_state == "STALE"
    assert scope.generation_id == resource.active_generation_id


@pytest.mark.parametrize("state", ["PENDING", "RUNNING", "FAILED"])
def test_resolve_active_generation_unready_rejected(
    db_session: Session, state: str
) -> None:
    resource = _create_resource(db_session, state=state)
    reader = SqlAlchemyGraphGenerationReader(db_session)

    with pytest.raises(GraphProjectionNotReadyError, match="not ready"):
        reader.resolve_active_generation(
            project_id=resource.project_id,
            architecture_version_id=resource.architecture_version_id,
        )


def test_resolve_active_generation_not_found(db_session: Session) -> None:
    reader = SqlAlchemyGraphGenerationReader(db_session)
    with pytest.raises(GraphProjectionNotFoundError):
        reader.resolve_active_generation(
            project_id=uuid4(),
            architecture_version_id=uuid4(),
        )


def test_resolve_active_generation_scope_mismatch(db_session: Session) -> None:
    resource = _create_resource(db_session, state="COMPLETED")
    reader = SqlAlchemyGraphGenerationReader(db_session)

    # Wrong project_id for this version
    with pytest.raises(GraphProjectionNotFoundError):
        reader.resolve_active_generation(
            project_id=uuid4(),
            architecture_version_id=resource.architecture_version_id,
        )


def test_resolve_active_generation_missing_metadata_integrity_error() -> None:
    from unittest.mock import MagicMock

    mock_session = MagicMock(spec=Session)
    mock_resource = MagicMock(spec=GraphProjectionResourceModel)
    proj_id = uuid4()
    ver_id = uuid4()
    mock_resource.project_id = proj_id
    mock_resource.architecture_version_id = ver_id
    mock_resource.state = "COMPLETED"
    mock_resource.active_generation_id = uuid4()
    mock_resource.active_projector_version = None  # Missing!
    mock_session.scalar.return_value = mock_resource

    reader = SqlAlchemyGraphGenerationReader(mock_session)

    with pytest.raises(GraphQueryIntegrityError, match="incomplete verification"):
        reader.resolve_active_generation(
            project_id=proj_id,
            architecture_version_id=ver_id,
        )


def test_verify_generation_still_active(db_session: Session) -> None:
    resource = _create_resource(db_session, state="COMPLETED")
    reader = SqlAlchemyGraphGenerationReader(db_session)

    # Active generation matches
    assert (
        reader.verify_generation_still_active(
            project_id=resource.project_id,
            architecture_version_id=resource.architecture_version_id,
            generation_id=resource.active_generation_id,  # type: ignore[arg-type]
        )
        is True
    )

    # Different generation
    assert (
        reader.verify_generation_still_active(
            project_id=resource.project_id,
            architecture_version_id=resource.architecture_version_id,
            generation_id=uuid4(),
        )
        is False
    )

    # Wrong project
    assert (
        reader.verify_generation_still_active(
            project_id=uuid4(),
            architecture_version_id=resource.architecture_version_id,
            generation_id=resource.active_generation_id,  # type: ignore[arg-type]
        )
        is False
    )


def test_fake_graph_generation_reader() -> None:
    reader = FakeGraphGenerationReader()
    project_id = uuid4()
    version_id = uuid4()
    gen_id = uuid4()

    scope = GraphReadScope(
        project_id=project_id,
        architecture_version_id=version_id,
        generation_id=gen_id,
        resource_state="COMPLETED",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        counts=ProjectionCounts(1, 1, 1, 0, 0),
    )

    # Not found
    with pytest.raises(GraphProjectionNotFoundError):
        reader.resolve_active_generation(project_id, version_id)

    # Set scope
    reader.set_scope(scope)
    resolved = reader.resolve_active_generation(project_id, version_id)
    assert resolved == scope
    assert reader.verify_generation_still_active(project_id, version_id, gen_id) is True
    assert (
        reader.verify_generation_still_active(project_id, version_id, uuid4()) is False
    )

    # Set unready
    reader.set_unready(project_id, version_id, "RUNNING")
    with pytest.raises(GraphProjectionNotReadyError):
        reader.resolve_active_generation(project_id, version_id)


def test_neo4j_deadline_guard_cancels_active_session() -> None:
    class StubTransaction:
        def __enter__(self) -> StubTransaction:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class StubSession:
        def __init__(self) -> None:
            self.cancelled = False

        def __enter__(self) -> StubSession:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def begin_transaction(self, *, timeout: float) -> StubTransaction:
            assert timeout == pytest.approx(0.01)
            return StubTransaction()

        def cancel(self) -> None:
            self.cancelled = True

    class StubDriver:
        def __init__(self, session: StubSession) -> None:
            self.stub_session = session

        def session(self, *, database: str) -> StubSession:
            assert database == "neo4j"
            return self.stub_session

    session = StubSession()
    repository = Neo4jGraphQueryRepository(StubDriver(session))  # type: ignore[arg-type]

    with pytest.raises(GraphQueryTimeoutError, match="total deadline"):
        with repository._bounded_transaction(0.01):
            time.sleep(0.03)

    assert session.cancelled is True
