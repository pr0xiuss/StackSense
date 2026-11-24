"""Opt-in real M1 -> four M4/ELK artifacts -> M5 -> fenced PG acceptance.

Uses the existing M4 application-only proof adapter, not production OS certification.
Requires the exact frozen M4 runtime; skips are never functional acceptance.
"""

# ruff: noqa: F401, F811
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, select
from sqlalchemy.orm import Session

from backend.platform.analysis.application.dependencies import (
    get_analysis_lifecycle_service,
    get_architecture_query_service,
    get_platform_repository_gateway,
)
from backend.platform.config import get_settings
from backend.platform.delivery.contracts import (
    BarrierReceipt,
    DiagramTemplate,
    WorkExecutionContext,
    WorkIdentity,
)
from backend.platform.delivery.persistence import DeliveryBundleModel, DeliveryWorkModel
from backend.platform.delivery.publication import PublicationUnitOfWork
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from backend.platform.diagrams.artifacts import LocalGeneratedArtifactStore
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.repository import (
    DatabaseReadAuthority,
    DiagramPublicationPort,
)
from backend.platform.diagrams.service import DiagramReader
from backend.platform.reports.artifacts import (
    CandidateReportWriter,
    LocalReportArtifactStore,
)
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.persistence import REPORT_TABLES, install_guards
from backend.platform.reports.preparation import ReportPreparer
from backend.platform.reports.render_runtime import IsolatedReportRenderRuntime
from backend.platform.reports.repository import (
    ReportDatabaseReadAuthority,
    ReportPublicationPort,
)
from backend.platform.reports.service import ReportWorkHandler
from tests.p5.diagrams.test_database import diagram_db
from tests.p5.diagrams.test_exports import Control
from tests.p5.diagrams.test_publication import lease_for
from tests.p5.integration.test_diagram_pipeline import diagram_pipeline

pytestmark = pytest.mark.skipif(
    os.environ.get("M4_B1_ESSENTIAL_PROOFS") != "1",
    reason="exact real M4 runtime and isolated PostgreSQL required",
)


def test_real_report_pipeline(diagram_db, diagram_pipeline, tmp_path):
    from contextlib import contextmanager

    engine, schema, _ = diagram_db
    scope, _, make_handler = diagram_pipeline
    for template in DiagramTemplate:
        lease, _ = lease_for(engine, template, scope)
        handler = make_handler(lease.identity.work.binding)
        output = handler.execute(
            WorkExecutionContext(
                attempt=lease.identity, deadline=lease.deadline, control=Control()
            )
        )
        with PublicationUnitOfWork(
            engine, timeout_seconds=5, lock_timeout_ms=1000
        ) as uow:

            def dependencies(session, receipt, lease=lease):
                def validate(item):
                    uow.enlist(DiagramPublicationPort).validate_ready(
                        item.accepted.reference, uow.context(item.prepared.attempt)
                    )

                SqlAlchemyDeliveryRepository(session).coordinate_dependencies(
                    lease.identity.work.bundle_id, validate, tentative=receipt
                )

            uow.complete(
                lease, output, DiagramPublicationPort, stage_dependencies=dependencies
            )
            uow.commit()
    with Session(engine) as session, session.begin():
        bundle = session.get(DeliveryBundleModel, lease.identity.work.bundle_id)
        barrier = BarrierReceipt.model_validate_json(json.dumps(bundle.barrier))
        row = session.scalar(
            select(DeliveryWorkModel).where(
                DeliveryWorkModel.bundle_id == bundle.id,
                DeliveryWorkModel.kind == "report",
            )
        )
        work = WorkIdentity.model_validate_json(json.dumps(row.identity))
        reservation = SqlAlchemyDeliveryRepository(session).reserve(
            row.id, scope.project_id, reservation_seconds=2, correlation_id="real-m5"
        )
    with Session(engine) as session, session.begin():
        report_lease = SqlAlchemyDeliveryRepository(session).claim(
            reservation[0],
            work.binding,
            "real-m5",
            max_executions=3,
            lease_seconds=120,
            execution_seconds=180,
        )
    assert report_lease is not None
    reader = DiagramReader(
        LocalGeneratedArtifactStore(
            DatabaseReadAuthority(engine, DiagramLimits(), actor_id=None),
            DiagramLimits(),
        ),
        DiagramLimits(),
    )
    metadata = MetaData()
    for table in REPORT_TABLES:
        table.to_metadata(metadata)
    with engine.begin() as connection:
        metadata.create_all(connection)
        install_guards(connection, schema)
    # Public source reads from the exact isolated canonical database.
    with (
        contextmanager(get_platform_repository_gateway)(get_settings()) as gateway,
        Session(engine) as session,
    ):
        preparer = ReportPreparer(
            get_architecture_query_service(session),
            get_analysis_lifecycle_service(session, gateway),
            reader,
        )
        root = tmp_path / "reports"
        handler = ReportWorkHandler(
            binding=work.binding,
            engine_or_session=engine,
            preparer=preparer,
            renderer=IsolatedReportRenderRuntime(),
            writer_factory=lambda a, c, g, limits: CandidateReportWriter(
                a, c, g, limits, root
            ),
        )
        context = WorkExecutionContext(
            attempt=report_lease.identity,
            deadline=report_lease.deadline,
            control=Control(),
            prerequisites=barrier,
        )
        output = handler.execute(context)
    with PublicationUnitOfWork(engine, timeout_seconds=5, lock_timeout_ms=1000) as uow:
        receipt = uow.complete(report_lease, output, ReportPublicationPort)
        uow.commit()
    store = LocalReportArtifactStore(
        ReportDatabaseReadAuthority(engine, ReportLimits()), root=root
    )
    handle = store.open_exact(scope, receipt.accepted.reference, "pdf")
    content = handle.read()
    handle.close()
    assert content.startswith(b"%PDF-")
    # New reader instance, no renderer/registry dependence after committed acceptance.
    restarted = LocalReportArtifactStore(
        ReportDatabaseReadAuthority(engine, ReportLimits()), root=root
    )
    handle = restarted.open_exact(scope, receipt.accepted.reference, "pdf")
    assert handle.read() == content
    handle.close()
