"""Internal cancellation preserves already expired attempts."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.platform.delivery.model import CancellationCause, CancellationDecision
from backend.platform.delivery.persistence import (
    DeliveryAttemptModel as Attempt,
)
from backend.platform.delivery.persistence import (
    DeliveryWorkModel as Work,
)
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from tests.p5.integration.test_delivery_postgres import claimed


def test_expired_attempt_stays_expired_when_logical_work_cancelled(delivery_engine):
    lease = claimed(delivery_engine)
    with Session(delivery_engine) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        session.execute(
            update(Attempt)
            .where(Attempt.id == lease.identity.attempt_id)
            .values(expires_at=repo.now() - timedelta(seconds=1))
        )
        command = CancellationDecision(
            CancellationCause.ADMINISTRATIVE_WITHDRAWAL,
            uuid4(),
            uuid4(),
            lease.identity.work.work_id,
            lease.identity.fence,
        )
        assert repo.cancel(lease.identity.work.scope.project_id, command)
    with Session(delivery_engine) as session:
        assert session.get(Attempt, lease.identity.attempt_id).state == "EXPIRED"
        work = session.get(Work, lease.identity.work.work_id)
        assert (
            work.state == "CANCELLED"
            and work.cancellation["invalidated_fence"] == lease.identity.fence
        )
