"""Tests for Analysis queue payload and broker publisher adapters."""

from uuid import uuid4

import pytest

from backend.platform.analysis.domain.constants import F1_CONTRACT_VERSION
from backend.platform.analysis.infra.queue import (
    AnalysisJobPayload,
    InMemoryAnalysisQueuePublisher,
)


def test_queue_payload_serialization_roundtrip() -> None:
    analysis_id = uuid4()
    job_id = uuid4()
    project_id = uuid4()
    correlation_id = str(uuid4())

    payload = AnalysisJobPayload(
        analysis_id=analysis_id,
        job_id=job_id,
        project_id=project_id,
        task_type="execute_analysis",
        contract_version=F1_CONTRACT_VERSION,
        correlation_id=correlation_id,
    )

    data = payload.to_dict()
    assert data["analysis_id"] == str(analysis_id)
    assert data["job_id"] == str(job_id)
    assert data["project_id"] == str(project_id)
    assert data["task_type"] == "execute_analysis"
    assert data["contract_version"] == F1_CONTRACT_VERSION
    assert data["correlation_id"] == correlation_id

    # Must contain ONLY approved identifier keys
    expected_keys = {
        "analysis_id",
        "job_id",
        "project_id",
        "task_type",
        "contract_version",
        "correlation_id",
    }
    assert set(data.keys()) == expected_keys

    # Deserialization
    reconstructed = AnalysisJobPayload.from_dict(data)
    assert reconstructed.analysis_id == analysis_id
    assert reconstructed.job_id == job_id
    assert reconstructed.project_id == project_id
    assert reconstructed.task_type == "execute_analysis"
    assert reconstructed.contract_version == F1_CONTRACT_VERSION
    assert reconstructed.correlation_id == correlation_id


def test_queue_payload_forbids_heavy_or_sensitive_fields() -> None:
    """Ensure queue payload never accepts or emits raw source, tokens, or artifacts."""
    payload = AnalysisJobPayload(
        analysis_id=uuid4(),
        job_id=uuid4(),
        project_id=uuid4(),
    )
    serialized = payload.to_dict()

    forbidden = {
        "source_bytes",
        "source_code",
        "artifacts",
        "credentials",
        "token",
        "password",
        "analysis_input",
        "configuration",
    }
    for key in forbidden:
        assert key not in serialized


def test_in_memory_queue_publisher() -> None:
    publisher = InMemoryAnalysisQueuePublisher()
    assert len(publisher.published_jobs) == 0

    p1 = AnalysisJobPayload(analysis_id=uuid4(), job_id=uuid4(), project_id=uuid4())
    p2 = AnalysisJobPayload(analysis_id=uuid4(), job_id=uuid4(), project_id=uuid4())

    publisher.publish_job(p1)
    publisher.publish_job(p2)

    assert len(publisher.published_jobs) == 2
    assert publisher.published_jobs[0].analysis_id == p1.analysis_id
    assert publisher.published_jobs[1].analysis_id == p2.analysis_id

    publisher.clear()
    assert len(publisher.published_jobs) == 0


def test_in_memory_queue_publisher_simulated_broker_failure() -> None:
    publisher = InMemoryAnalysisQueuePublisher(should_fail=True)
    payload = AnalysisJobPayload(
        analysis_id=uuid4(), job_id=uuid4(), project_id=uuid4()
    )

    with pytest.raises(
        ConnectionError, match="Simulated message broker connection failure"
    ):
        publisher.publish_job(payload)
