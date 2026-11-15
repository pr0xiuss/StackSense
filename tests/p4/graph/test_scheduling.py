"""Celery routing and execution-capability gate tests."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.config import Settings
from backend.platform.projects.infra.base import Base
from backend.worker.celery_app import celery_app
from backend.worker.graph_tasks import graph_projection_execution_ready


def test_graph_tasks_are_routed_without_changing_analysis_default() -> None:
    settings = Settings()

    assert celery_app.conf.task_default_queue == settings.analysis_queue_name
    assert celery_app.conf.task_routes["stacksense.execute_analysis"] == {
        "queue": settings.analysis_queue_name
    }
    assert celery_app.conf.task_routes["stacksense.execute_graph_projection"] == {
        "queue": settings.graph_queue_name
    }
    assert celery_app.conf.beat_schedule["reconcile-graph-projections"]["options"] == {
        "queue": settings.graph_maintenance_queue_name
    }
    assert celery_app.conf.beat_schedule["graph-runtime-heartbeat"]["options"] == {
        "queue": settings.graph_maintenance_queue_name
    }


def test_dispatch_fails_closed_without_registered_m2_executor() -> None:
    settings = Settings(graph_projection_dispatch_enabled=True)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert graph_projection_execution_ready(session, settings) is False
    engine.dispose()


def test_example_discovery_interval_is_applied_to_fresh_beat_configuration() -> None:
    root = Path(__file__).resolve().parents[3]
    interval_line = next(
        line
        for line in (root / ".env.example").read_text().splitlines()
        if line.startswith("GRAPH_RECONCILIATION_INTERVAL_SECONDS=")
    )
    interval = interval_line.split("=", 1)[1]
    assert interval == "5"
    # Celery captures Settings at import: test the actual application in a fresh
    # interpreter, not a cached module or an isolated Settings object alone.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from backend.worker.celery_app import celery_app; "
            "entry = celery_app.conf.beat_schedule['reconcile-graph-projections']; "
            "print(json.dumps({'interval': entry['schedule'], 'task': entry['task']}))",
        ],
        cwd=root,
        env={**os.environ, "GRAPH_RECONCILIATION_INTERVAL_SECONDS": interval},
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert json.loads(result.stdout) == {
        "interval": 5,
        "task": "stacksense.reconcile_graph_projections",
    }


def test_discovery_tuning_preserves_minimum_and_recovery_defaults() -> None:
    settings = Settings(_env_file=None, graph_reconciliation_interval_seconds=5)
    assert settings.graph_reconciliation_interval_seconds == 5
    assert settings.graph_dispatch_recovery_seconds == 60
    assert settings.graph_lease_duration_seconds == 120
    assert settings.graph_retry_backoff_seconds == 15
    with pytest.raises(ValidationError):
        Settings(_env_file=None, graph_reconciliation_interval_seconds=4)
