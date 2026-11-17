"""Bounded durable-work measurements on an explicitly isolated PostgreSQL DB."""

import json
import platform
from time import perf_counter

try:
    import resource
except ImportError:
    resource = None  # type: ignore[assignment]


from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.platform.delivery.model import Eligibility
from backend.platform.delivery.persistence import (
    DeliveryBundleModel as Bundle,
)
from backend.platform.delivery.persistence import (
    DeliveryWorkModel as Work,
)
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from tests.p5.delivery.test_contracts import scope
from tests.p5.delivery.test_rollout import budgets, coordinator
from tests.p5.integration.test_delivery_postgres import policy


def current_rss_mib():
    # Current per-process RSS, not a threshold against pytest lifetime peak.
    try:
        with open("/proc/self/status") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return None


def test_bounded_backfill_dispatch_measurements(delivery_engine):
    selected, started, before = policy(), perf_counter(), current_rss_mib()
    with Session(delivery_engine) as session, session.begin():
        for _ in range(25):
            SqlAlchemyDeliveryRepository(session).ensure_bundle(
                scope(),
                selected,
                Eligibility.ELIGIBLE,
                revisit_seconds=1.0,
                runtime_profile=budgets().model_dump(mode="json"),
            )
    seed_seconds = perf_counter() - started
    runtime = coordinator(delivery_engine)
    runtime.heartbeat("test-worker")
    started = perf_counter()
    sent = runtime.dispatch()
    dispatch_seconds = perf_counter() - started
    assert 0 < sent <= runtime.budgets.max_items
    with Session(delivery_engine) as session:
        assert session.scalar(select(func.count()).select_from(Bundle)) == 25
        assert session.scalar(select(func.count()).select_from(Work)) == 125
        assert session.scalar(select(func.sum(Work.executions))) == 0
    print(
        "P5_B2_MEASUREMENT "
        + json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "bundles": 25,
                "work_rows": 125,
                "seed_seconds": round(seed_seconds, 6),
                "dispatch_window": runtime.budgets.max_items,
                "sent": sent,
                "dispatch_seconds": round(dispatch_seconds, 6),
                "current_rss_before_mib": before,
                "current_rss_after_mib": current_rss_mib(),
                "parent_lifetime_peak_mib_informational_only": (
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                    if resource is not None
                    else None
                ),
            }
        )
    )
