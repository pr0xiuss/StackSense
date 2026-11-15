"""Strict identifier-only graph worker contract and publishing port."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.platform.graph.model import WORKER_CONTRACT_VERSION, ProjectionWorkClaim


class ProjectionWorkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    projection_id: UUID
    attempt_id: UUID
    project_id: UUID
    architecture_version_id: UUID
    generation_id: UUID
    contract_version: str
    correlation_id: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def _validate_contract(self) -> ProjectionWorkPayload:
        if self.contract_version != WORKER_CONTRACT_VERSION:
            raise ValueError("unsupported graph worker contract version")
        return self

    def to_claim(self) -> ProjectionWorkClaim:
        return ProjectionWorkClaim(**self.model_dump())


class ProjectionPublisher(Protocol):
    def publish(self, payload: ProjectionWorkPayload) -> None: ...


class CelerySender(Protocol):
    def send_task(
        self, name: str, *, kwargs: dict[str, object], queue: str
    ) -> object: ...


GRAPH_EXECUTION_TASK_NAME = "stacksense.execute_graph_projection"
GRAPH_CLEANUP_TASK_NAME = "stacksense.cleanup_graph_generation"


class InMemoryProjectionPublisher:
    """Deterministic publisher used by lifecycle unit tests."""

    def __init__(self) -> None:
        self.published: list[ProjectionWorkPayload] = []

    def publish(self, payload: ProjectionWorkPayload) -> None:
        self.published.append(payload)


class CeleryProjectionPublisher:
    """Publish the strict P4-W1 envelope to the dedicated graph queue."""

    def __init__(self, *, queue_name: str, celery: CelerySender | None = None) -> None:
        if not queue_name.strip():
            raise ValueError("graph queue name must not be empty")
        self._queue_name = queue_name
        self._celery = celery

    def publish(self, payload: ProjectionWorkPayload) -> None:
        app = self._celery
        if app is None:
            from backend.worker.celery_app import celery_app

            app = celery_app
        app.send_task(
            GRAPH_EXECUTION_TASK_NAME,
            kwargs=payload.model_dump(mode="json"),
            queue=self._queue_name,
        )


__all__ = [
    "CeleryProjectionPublisher",
    "GRAPH_CLEANUP_TASK_NAME",
    "GRAPH_EXECUTION_TASK_NAME",
    "InMemoryProjectionPublisher",
    "ProjectionPublisher",
    "ProjectionWorkPayload",
]
