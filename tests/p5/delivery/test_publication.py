"""No production activation is possible with an unauthorized UoW."""

import pytest

from backend.platform.delivery.publication import (
    PublicationContractViolation,
    PublicationUnitOfWork,
)


def test_outer_commit_requires_final_authorization(delivery_engine):
    with PublicationUnitOfWork(
        delivery_engine, timeout_seconds=2.0, lock_timeout_ms=500
    ) as uow:
        with pytest.raises(PublicationContractViolation):
            uow.commit()
