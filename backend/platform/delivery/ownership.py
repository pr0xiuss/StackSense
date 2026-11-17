"""Public read-only M1 retirement port for producer cleanup exclusion.

No cleanup, liveness mutation, secret, or deletion authority is provided. A
terminal attempt UUID never reopens, so a committed retirement observation is
stable without holding M1 locks across producer cleanup/storage operations.
"""

import json

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AttemptIdentity,
    AttemptRetirement,
    DeliveryContractError,
    PublicationReceipt,
    VersionScope,
    WorkIdentity,
)
from backend.platform.delivery.persistence import DeliveryAttemptModel as Attempt
from backend.platform.delivery.persistence import DeliveryBundleModel as Bundle
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work


class SqlAlchemyAttemptRetirementReader:
    def __init__(
        self, engine: Engine, *, timeout_seconds: float, lock_timeout_ms: int
    ) -> None:
        if timeout_seconds <= 0 or lock_timeout_ms <= 0:
            raise ValueError("retirement reads require explicit positive budgets")
        self.engine, self.timeout_seconds, self.lock_timeout_ms = (
            engine,
            timeout_seconds,
            lock_timeout_ms,
        )

    def read_retirement(self, attempt: AttemptIdentity) -> AttemptRetirement | None:
        attempt = AttemptIdentity.model_validate(attempt)
        with Session(self.engine, autoflush=False) as session, session.begin():
            session.execute(
                select(
                    func.set_config(
                        "statement_timeout",
                        str(max(1, int(self.timeout_seconds * 1000))),
                        True,
                    )
                )
            )
            session.execute(
                select(func.set_config("lock_timeout", str(self.lock_timeout_ms), True))
            )
            found = session.execute(
                select(Attempt, Work, Bundle, Output)
                .select_from(Attempt)
                .join(Work, Work.id == Attempt.work_id)
                .join(Bundle, Bundle.id == Work.bundle_id)
                .outerjoin(Output, Output.attempt_id == Attempt.id)
                .where(
                    Attempt.id == attempt.attempt_id,
                    Bundle.project_id == attempt.work.scope.project_id,
                )
            ).one_or_none()
            if found is None:
                return None
            row, work, bundle, output = found
            if (
                AttemptIdentity.model_validate_json(json.dumps(row.identity)) != attempt
                or WorkIdentity.model_validate_json(json.dumps(work.identity))
                != attempt.work
                or VersionScope.model_validate_json(json.dumps(bundle.scope))
                != attempt.work.scope
                or row.work_id != attempt.work.work_id
                or work.bundle_id != attempt.work.bundle_id
                or row.fence != attempt.fence
                or row.ordinal != attempt.ordinal
                or row.candidate_id != attempt.candidate_id
            ):
                raise DeliveryContractError("retirement ownership mismatch")
            if row.state == "RUNNING":
                return None  # Even an expired wall-clock lease is not retirement.
            publication = None
            if output is not None:
                publication = PublicationReceipt.model_validate_json(
                    json.dumps(output.receipt)
                )
                if (
                    output.work_id != work.id
                    or output.bundle_id != bundle.id
                    or output.id != publication.receipt_id
                    or output.fence != attempt.fence
                ):
                    raise DeliveryContractError("retirement receipt mismatch")
            return AttemptRetirement.model_validate(
                {
                    "attempt": attempt,
                    "outcome": row.state,
                    "ended_at": row.ended_at,
                    "publication": publication,
                }
            )
