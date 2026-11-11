"""Celery routing and execution-capability gate tests."""

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
