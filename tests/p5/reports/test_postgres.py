"""Real report PostgreSQL/filesystem boundaries; upstream DTOs are unit fixtures.

This suite does not claim full M1/M4/ELK end-to-end acceptance.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.platform.delivery.publication import (
    GuardedEnlistedSession,
    PublicationContext,
    PublicationGuard,
)
from backend.platform.reports.artifacts import (
    CandidateReportWriter,
    LocalReportArtifactStore,
)
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.persistence import REPORT_TABLES, install_guards
from backend.platform.reports.persistence import ReportGenerationModel as Generation
from backend.platform.reports.persistence import ReportReadPinModel as Pin
from backend.platform.reports.preparation import ReportPreparer
from backend.platform.reports.repository import (
    ReportDatabaseReadAuthority,
    ReportPublicationPort,
)
from backend.platform.reports.service import ReportWorkHandler
from tests.p5.reports.conftest import (
    FakeAnalysisLifecycleService,
    FakeArchitectureQueryService,
    FakeDiagramReader,
    sample_work_context,
)


@pytest.fixture
def report_db(delivery_engine):
    engine = delivery_engine
    schema = engine.get_execution_options()["schema_translate_map"][None]
    metadata = MetaData()
    for table in REPORT_TABLES:
        table.to_metadata(metadata)
    with engine.begin() as connection:
        metadata.create_all(connection)
        install_guards(connection, schema)
    return engine


@pytest.fixture
def published_report(report_db, tmp_path):
    context, diagrams = sample_work_context()
    preparer = ReportPreparer(
        FakeArchitectureQueryService(),
        FakeAnalysisLifecycleService(),
        FakeDiagramReader(diagrams),
    )
    handler = ReportWorkHandler(
        binding=context.attempt.work.binding,
        engine_or_session=report_db,
        preparer=preparer,
        renderer=ReportLabPdfRenderer(),
        writer_factory=lambda a, c, g, limits: CandidateReportWriter(
            a, c, g, limits, tmp_path
        ),
    )
    output = handler.execute(context)
    # A second connection independently sees staging before publication starts.
    with Session(report_db) as session:
        assert (
            session.get(Generation, output.candidate.generation_id).state
            == "SEALED_VERIFIED"
        )
    with Session(report_db) as session:
        port = ReportPublicationPort(
            GuardedEnlistedSession(
                session, guard=PublicationGuard(), check=lambda: None
            )
        )
        accepted = port.publish_prepared(
            output,
            PublicationContext(
                transaction_id=uuid4(),
                attempt=context.attempt,
                deadline=datetime.now(UTC) + timedelta(seconds=5),
            ),
        )
        session.commit()
    return context, accepted.reference, tmp_path


def test_pg_trusted_exact_reads_and_foreign_reference_rejection(
    report_db, published_report
):
    context, reference, root = published_report
    authority = ReportDatabaseReadAuthority(report_db, ReportLimits())
    store = LocalReportArtifactStore(authority, root=root)
    handle = store.open_exact(context.attempt.work.scope, reference, "pdf")
    data = handle.read()
    handle.close()
    assert data.startswith(b"%PDF-")
    for changes in (
        {"artifact_id": uuid4()},
        {"input_fingerprint": "0" * 64},
        {"generation_id": uuid4()},
    ):
        with pytest.raises(ValueError):
            authority.recheck(
                context.attempt.work.scope, reference.model_copy(update=changes)
            )
    foreign = context.attempt.work.scope.model_copy(update={"project_id": uuid4()})
    with pytest.raises(ValueError):
        authority.recheck(foreign, reference.model_copy(update={"scope": foreign}))
    with Session(report_db) as session:
        assert not session.scalars(select(Pin)).all()


def test_pg_accepted_content_is_immutable_and_reads_detect_corruption(
    report_db, published_report
):
    context, reference, root = published_report
    with pytest.raises(DBAPIError), report_db.begin() as connection:
        connection.execute(
            update(Generation)
            .where(Generation.id == reference.generation_id)
            .values(pdf_sha256="0" * 64)
        )
    path = root / "sealed" / str(reference.generation_id) / "report.pdf"
    original = path.read_bytes()
    path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    store = LocalReportArtifactStore(
        ReportDatabaseReadAuthority(report_db, ReportLimits()), root=root
    )
    with pytest.raises(ValueError):
        store.open_exact(context.attempt.work.scope, reference, "pdf")


def test_pg_expired_pins_do_not_exhaust_read_quota(report_db, published_report):
    context, reference, root = published_report
    now = datetime.now(UTC)
    with Session(report_db) as session, session.begin():
        session.add(
            Pin(
                id=uuid4(),
                generation_id=reference.generation_id,
                actor_id=None,
                purpose="export",
                created_at=now - timedelta(seconds=60),
                expires_at=now - timedelta(seconds=1),
                token_hash=hashlib.sha256(b"expired").hexdigest(),
            )
        )
    limits = ReportLimits(max_pins_per_generation=1)
    authority = ReportDatabaseReadAuthority(report_db, limits)
    with authority.pinned(context.attempt.work.scope, reference):
        with Session(report_db) as session:
            assert len(session.scalars(select(Pin)).all()) == 1


def test_pg_deadline_cancels_actual_statement(report_db):
    from backend.platform.reports.repository import metadata_operation, metadata_session

    start = monotonic()
    with pytest.raises((TimeoutError, DBAPIError)):
        with (
            metadata_operation(monotonic() + 1.2),
            metadata_session(report_db) as session,
        ):
            session.execute(text("SELECT pg_sleep(10)"))
    assert monotonic() - start < 3
