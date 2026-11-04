"""Queue payload contracts and broker publishers for Analysis background jobs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from backend.platform.analysis.domain.constants import F1_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class AnalysisJobPayload:
    """Identifier-only message payload published to RabbitMQ/Celery."""

    analysis_id: UUID
    job_id: UUID
    project_id: UUID
    task_type: str = "execute_analysis"
    contract_version: str = F1_CONTRACT_VERSION
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, str]:
        """Serialize payload to JSON-compatible dictionary."""
        return {
            "analysis_id": str(self.analysis_id),
            "job_id": str(self.job_id),
            "project_id": str(self.project_id),
            "task_type": self.task_type,
            "contract_version": self.contract_version,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisJobPayload:
        """Deserialize payload from dictionary."""
        return cls(
            analysis_id=UUID(str(data["analysis_id"])),
            job_id=UUID(str(data["job_id"])),
            project_id=UUID(str(data["project_id"])),
            task_type=str(data.get("task_type", "execute_analysis")),
            contract_version=str(data.get("contract_version", F1_CONTRACT_VERSION)),
            correlation_id=str(data.get("correlation_id", uuid4())),
        )


class AnalysisQueuePublisher(ABC):
    """Abstract port for publishing analysis background execution jobs."""

    @abstractmethod
    def publish_job(self, payload: AnalysisJobPayload) -> None:
        """Publish execution payload to the message broker.

        Raises:
            Exception: If broker dispatch fails.
        """
        raise NotImplementedError


class InMemoryAnalysisQueuePublisher(AnalysisQueuePublisher):
    """Deterministic in-memory queue publisher for testing and local execution."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.published_jobs: list[AnalysisJobPayload] = []
        self.should_fail = should_fail

    def publish_job(self, payload: AnalysisJobPayload) -> None:
        """Record published payload or simulate broker outage."""
        if self.should_fail:
            raise ConnectionError("Simulated message broker connection failure.")
        self.published_jobs.append(payload)

    def clear(self) -> None:
        """Clear recorded payloads."""
        self.published_jobs.clear()


class CeleryAnalysisQueuePublisher(AnalysisQueuePublisher):
    """Celery-backed implementation publishing to RabbitMQ."""

    def __init__(self, queue_name: str = "analysis.jobs") -> None:
        self.queue_name = queue_name

    def publish_job(self, payload: AnalysisJobPayload) -> None:
        """Dispatch task to Celery worker via send_task with identifier-only payload."""
        from backend.worker.celery_app import celery_app

        celery_app.send_task(
            "stacksense.execute_analysis",
            kwargs=payload.to_dict(),
            queue=self.queue_name,
        )
