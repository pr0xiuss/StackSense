"""Discovery revisits pending eligibility independently of the sweep cursor."""

from dataclasses import replace
from datetime import timedelta

from sqlalchemy import select

from backend.platform.delivery.persistence import DeliveryBundleModel as Bundle
from backend.platform.delivery.persistence import DeliveryDiscoveryModel as Discovery
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from tests.p5.delivery.test_rollout import coordinator
from tests.p5.delivery.test_source import PublicSourceFixture


def test_pending_analysis_revisited_without_restarting_scan(delivery_engine):
    source = PublicSourceFixture()
    source.analysis = replace(source.analysis, status="running")
    runtime = coordinator(delivery_engine, reader_source=source)
    runtime.discover()
    with runtime.session() as session, session.begin():
        bundle = session.scalars(select(Bundle)).one()
        assert bundle.eligibility == "WAITING_FOR_ANALYSIS"
        bundle.eligibility_retry_at = SqlAlchemyDeliveryRepository(
            session
        ).now() - timedelta(seconds=1)
        assert session.scalar(select(Work.id)) is None
    source.analysis = replace(source.analysis, status="completed")
    assert runtime.revisit() == 1
    with runtime.session() as session:
        assert session.scalars(select(Bundle)).one().eligibility == "ELIGIBLE"
        assert len(tuple(session.scalars(select(Work)))) == 5
        assert session.scalars(select(Discovery)).one().cursor is None


def test_invalid_header_is_durably_quarantined_without_work(delivery_engine):
    source = PublicSourceFixture()
    source.header = replace(source.header, contract_version="unsupported")
    source.headers = [source.header]
    runtime = coordinator(delivery_engine, reader_source=source)
    assert runtime.discover() == 1
    with runtime.session() as session:
        state = session.scalars(select(Discovery)).one()
        assert (
            state.pending["quarantine"][str(source.header.architecture_version_id)][
                "code"
            ]
            == "source_integrity_failed"
        )
        assert session.scalar(select(Bundle.id)) is None
        assert session.scalar(select(Work.id)) is None
