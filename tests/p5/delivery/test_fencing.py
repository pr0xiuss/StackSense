"""Wrong worker/secret/project cannot renew or publish another execution."""

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.platform.delivery.repository import (
    DeliveryOwnershipLost,
    SqlAlchemyDeliveryRepository,
)
from tests.p5.integration.test_delivery_postgres import claimed


def test_forged_worker_secret_and_project_fail_closed(delivery_engine):
    lease = claimed(delivery_engine)
    for forged in (
        replace(lease, worker_id="different"),
        replace(lease, secret="wrong"),
    ):
        with Session(delivery_engine) as session, session.begin():
            repo = SqlAlchemyDeliveryRepository(session)
            assert not repo.renew(forged, lease_seconds=30.0)
            with pytest.raises(DeliveryOwnershipLost):
                repo.live(forged, lock=True)
    with Session(delivery_engine) as session, session.begin():
        with pytest.raises(DeliveryOwnershipLost):
            SqlAlchemyDeliveryRepository(session).lock_work(
                lease.identity.work.work_id, uuid4()
            )
