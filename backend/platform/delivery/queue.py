"""Identifier-only transport; PostgreSQL durable intent owns retries."""

from typing import Any, Protocol

from backend.platform.delivery.contracts import DeliveryWorkPayload

EXECUTE_TASK = "stacksense.execute_delivery_work"
RECONCILE_TASK = "stacksense.reconcile_delivery"
HEARTBEAT_TASK = "stacksense.delivery_runtime_heartbeat"


class DeliveryPublisher(Protocol):
    def publish(self, payload: DeliveryWorkPayload) -> None: ...


class CeleryDeliveryPublisher:
    def __init__(
        self,
        app: Any,
        *,
        queue: str,
        timeout_seconds: float,
        hard_timeout_seconds: float | None = None,
    ) -> None:
        self._app, self._queue, self._timeout = app, queue, timeout_seconds
        self._hard_timeout = hard_timeout_seconds

    def publish(self, payload: DeliveryWorkPayload) -> None:
        payload = DeliveryWorkPayload.model_validate(payload)
        # A bounded connection/publish attempt, never Celery's independent retry
        # loop. Broker success is still ambiguous until durable bookkeeping.
        with self._app.connection_for_write(
            connect_timeout=self._timeout,
            transport_options={
                **(self._app.conf.broker_transport_options or {}),
                "read_timeout": self._timeout,
                "write_timeout": self._timeout,
            },
        ) as connection:
            connection.ensure_connection(max_retries=0, timeout=self._timeout)
            with self._app.amqp.Producer(connection) as producer:
                self._app.send_task(
                    EXECUTE_TASK,
                    kwargs=payload.model_dump(mode="json"),
                    queue=self._queue,
                    producer=producer,
                    retry=False,
                    timeout=self._timeout,
                    **(
                        {"time_limit": self._hard_timeout}
                        if self._hard_timeout is not None
                        else {}
                    ),
                )
