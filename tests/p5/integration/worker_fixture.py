"""Isolated real Celery worker fixture. Never imported into production wiring."""

import os

from celery import signals
from sqlalchemy import Column, MetaData, String, Table, Uuid, create_engine

from backend.platform.delivery.registry import HandlerRegistration, WorkHandlerRegistry
from tests.p5.delivery.test_contracts import binding
from tests.p5.delivery.test_rollout import coordinator
from tests.p5.integration.test_delivery_postgres import FixturePort, prepared


def main():
    import backend.worker.delivery_tasks as tasks
    from backend.worker.celery_app import celery_app

    engine = create_engine(
        os.environ["P5_TEST_DATABASE_URL"], connect_args={"connect_timeout": 5}
    ).execution_options(schema_translate_map={None: os.environ["P5_TEST_SCHEMA"]})
    table = Table(
        "fixture_producer",
        MetaData(),
        Column("id", Uuid, primary_key=True),
        Column("digest", String, nullable=False),
    )

    class Handler:
        def execute(self, context):
            if os.environ.get("P5_TEST_PAUSE_AFTER_CLAIM") or (
                os.environ.get("P5_TEST_PAUSE_DATA_FLOW")
                and context.attempt.work.binding.slot.template == "data_flow"
            ):
                import time

                while True:
                    time.sleep(0.1)  # Deliberate fixture crash window.
            # Fixture preparation only; no actual output algorithms.
            from types import SimpleNamespace

            self.candidate = prepared(SimpleNamespace(identity=context.attempt))
            return self.candidate

        def factory(self, session):
            return FixturePort(session, table, None)

    handler = Handler()
    registry = WorkHandlerRegistry(
        (HandlerRegistration(binding(), handler, handler.factory),)
    )
    if os.environ.get("P5_TEST_ALL_HANDLERS"):
        from tests.p5.delivery.test_barrier import complete_registry

        registry = complete_registry(table)
        if os.environ.get("P5_TEST_PAUSE_DATA_FLOW"):
            original = registry.resolve(
                next(b for b in registry.profiles if b.slot.template == "data_flow")
            )

            class Paused:
                def execute(self, context):
                    import time

                    while True:
                        time.sleep(0.1)

            registry = WorkHandlerRegistry(
                tuple(
                    (
                        HandlerRegistration(b, Paused(), original.publication_factory)
                        if b.slot.template == "data_flow"
                        else registry.resolve(b)
                    )
                    for b in registry.profiles
                )
            )
    runtime = coordinator(
        engine,
        registry=registry,
        queue=os.environ["P5_TEST_QUEUE"],
        workers=("test-worker@fixture",),
    )
    tasks._runtime = lambda: runtime

    @signals.worker_ready.connect(weak=False)
    def ready(sender=None, **kwargs):
        runtime.heartbeat(str(sender.hostname))

    celery_app.conf.broker_url = os.environ["RABBITMQ_TEST_URL"]
    celery_app.conf.broker_connection_retry_on_startup = False
    celery_app.worker_main(
        [
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "--loglevel=WARNING",
            "--without-gossip",
            "--without-mingle",
            "--hostname=test-worker@fixture",
            "--queues=" + os.environ["P5_TEST_QUEUE"],
        ]
    )


if __name__ == "__main__":
    main()
