"""Unit tests for Analysis, Job, and Stage domain entities and lifecycle."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.platform.analysis.domain.analysis import (
    Analysis,
    AnalysisCompleteness,
    AnalysisConfiguration,
    AnalysisProgress,
)
from backend.platform.analysis.domain.constants import (
    ANALYSIS_TRANSITION_MATRIX,
    TERMINAL_ANALYSIS_STATES,
    TERMINAL_JOB_STATES,
    TERMINAL_STAGE_STATES,
    AnalysisStatus,
    JobStatus,
    StageStatus,
)
from backend.platform.analysis.domain.job import AnalysisJob, AnalysisStage
from backend.platform.errors import AnalysisStateConflictError


def _create_sample_analysis(
    status: AnalysisStatus = AnalysisStatus.CREATED,
) -> Analysis:
    now = datetime.now(UTC)
    return Analysis(
        id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        status=status,
        configuration=AnalysisConfiguration(),
        created_at=now,
        updated_at=now,
    )


def _create_sample_job(status: JobStatus = JobStatus.PENDING) -> AnalysisJob:
    now = datetime.now(UTC)
    return AnalysisJob(
        id=uuid4(),
        analysis_id=uuid4(),
        project_id=uuid4(),
        status=status,
        created_at=now,
        updated_at=now,
    )


def _create_sample_stage(status: StageStatus = StageStatus.PENDING) -> AnalysisStage:
    now = datetime.now(UTC)
    return AnalysisStage(
        id=uuid4(),
        analysis_id=uuid4(),
        stage_name="inventory",
        status=status,
        order=1,
        created_at=now,
        updated_at=now,
    )


# --- Immutability & Slot Tests ---


def test_analysis_is_immutable_and_slotted() -> None:
    analysis = _create_sample_analysis()
    with pytest.raises(AttributeError):
        analysis.status = AnalysisStatus.RUNNING  # type: ignore[misc]

    assert hasattr(analysis, "__slots__")


def test_analysis_configuration_is_immutable() -> None:
    config = AnalysisConfiguration()
    with pytest.raises(AttributeError):
        config.timeout_seconds = 100  # type: ignore[misc]
    assert hasattr(config, "__slots__")


def test_analysis_completeness_is_immutable() -> None:
    completeness = AnalysisCompleteness(analyzed_files_count=10, is_partial=False)
    with pytest.raises(AttributeError):
        completeness.analyzed_files_count = 20  # type: ignore[misc]
    assert hasattr(completeness, "__slots__")


def test_analysis_progress_is_immutable() -> None:
    progress = AnalysisProgress(
        current_stage="inventory", processed_items=5, total_items=10
    )
    with pytest.raises(AttributeError):
        progress.processed_items = 6  # type: ignore[misc]
    assert hasattr(progress, "__slots__")


def test_analysis_job_and_stage_are_immutable() -> None:
    job = _create_sample_job()
    with pytest.raises(AttributeError):
        job.status = JobStatus.RUNNING  # type: ignore[misc]
    assert hasattr(job, "__slots__")

    stage = _create_sample_stage()
    with pytest.raises(AttributeError):
        stage.status = StageStatus.RUNNING  # type: ignore[misc]
    assert hasattr(stage, "__slots__")


# --- Analysis Lifecycle Golden Paths & Transitions ---


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (AnalysisStatus.CREATED, AnalysisStatus.QUEUED),
        (AnalysisStatus.CREATED, AnalysisStatus.FAILED),
        (AnalysisStatus.QUEUED, AnalysisStatus.RUNNING),
        (AnalysisStatus.QUEUED, AnalysisStatus.CANCELLED),
        (AnalysisStatus.RUNNING, AnalysisStatus.COMPLETED),
        (AnalysisStatus.RUNNING, AnalysisStatus.PARTIAL),
        (AnalysisStatus.RUNNING, AnalysisStatus.CANCEL_REQUESTED),
        (AnalysisStatus.RUNNING, AnalysisStatus.TIMEOUT),
        (AnalysisStatus.RUNNING, AnalysisStatus.FAILED),
        (AnalysisStatus.CANCEL_REQUESTED, AnalysisStatus.CANCELLED),
        (AnalysisStatus.TIMEOUT, AnalysisStatus.FAILED),
        (AnalysisStatus.PARTIAL, AnalysisStatus.COMPLETED_WITH_WARNINGS),
        (AnalysisStatus.PARTIAL, AnalysisStatus.FAILED),
    ],
)
def test_valid_analysis_transitions(
    source: AnalysisStatus, target: AnalysisStatus
) -> None:
    analysis = _create_sample_analysis(status=source)
    assert analysis.can_transition_to(target)

    now = datetime.now(UTC)
    updated = analysis.transition_to(target, updated_at=now)

    assert updated.status == target
    assert updated.version == analysis.version + 1
    assert updated.updated_at == now

    if target == AnalysisStatus.RUNNING:
        assert updated.started_at == now
    if target in TERMINAL_ANALYSIS_STATES:
        assert updated.completed_at == now
        assert updated.is_terminal is True


def test_terminal_states_cannot_transition() -> None:
    for terminal_status in TERMINAL_ANALYSIS_STATES:
        analysis = _create_sample_analysis(status=terminal_status)
        assert analysis.is_terminal is True

        for any_status in AnalysisStatus:
            assert not analysis.can_transition_to(any_status)
            with pytest.raises(AnalysisStateConflictError):
                analysis.transition_to(any_status, updated_at=datetime.now(UTC))


@pytest.mark.parametrize(
    ("source", "invalid_target"),
    [
        (AnalysisStatus.CREATED, AnalysisStatus.RUNNING),
        (AnalysisStatus.CREATED, AnalysisStatus.COMPLETED),
        (AnalysisStatus.QUEUED, AnalysisStatus.COMPLETED),
        (AnalysisStatus.QUEUED, AnalysisStatus.CREATED),
        (AnalysisStatus.RUNNING, AnalysisStatus.CREATED),
        (AnalysisStatus.RUNNING, AnalysisStatus.QUEUED),
        (AnalysisStatus.CANCEL_REQUESTED, AnalysisStatus.COMPLETED),
        (AnalysisStatus.CANCEL_REQUESTED, AnalysisStatus.RUNNING),
        (AnalysisStatus.TIMEOUT, AnalysisStatus.COMPLETED),
        (AnalysisStatus.TIMEOUT, AnalysisStatus.RUNNING),
        (AnalysisStatus.PARTIAL, AnalysisStatus.COMPLETED),
    ],
)
def test_invalid_analysis_transitions_raise_conflict(
    source: AnalysisStatus,
    invalid_target: AnalysisStatus,
) -> None:
    analysis = _create_sample_analysis(status=source)
    assert not analysis.can_transition_to(invalid_target)

    with pytest.raises(AnalysisStateConflictError) as exc_info:
        analysis.transition_to(invalid_target, updated_at=datetime.now(UTC))

    assert exc_info.value.code == "analysis_state_conflict"


def test_transition_matrix_completeness() -> None:
    """Ensure every status is defined in ANALYSIS_TRANSITION_MATRIX."""
    for status in AnalysisStatus:
        assert status in ANALYSIS_TRANSITION_MATRIX


# --- Job Lifecycle Tests ---


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (JobStatus.PENDING, JobStatus.QUEUED),
        (JobStatus.PENDING, JobStatus.RUNNING),
        (JobStatus.QUEUED, JobStatus.RUNNING),
        (JobStatus.QUEUED, JobStatus.CANCELLED),
        (JobStatus.RUNNING, JobStatus.RETRYING),
        (JobStatus.RUNNING, JobStatus.COMPLETED),
        (JobStatus.RUNNING, JobStatus.FAILED),
        (JobStatus.RUNNING, JobStatus.CANCELLED),
        (JobStatus.RETRYING, JobStatus.QUEUED),
        (JobStatus.RETRYING, JobStatus.RUNNING),
        (JobStatus.RETRYING, JobStatus.FAILED),
    ],
)
def test_valid_job_transitions(source: JobStatus, target: JobStatus) -> None:
    job = _create_sample_job(status=source)
    assert job.can_transition_to(target)

    now = datetime.now(UTC)
    updated = job.transition_to(
        target, updated_at=now, increment_attempt=(target == JobStatus.RETRYING)
    )

    assert updated.status == target
    assert updated.version == job.version + 1
    if target == JobStatus.RETRYING:
        assert updated.attempt == job.attempt + 1


def test_terminal_job_cannot_transition() -> None:
    for status in TERMINAL_JOB_STATES:
        job = _create_sample_job(status=status)
        assert job.is_terminal is True
        for target in JobStatus:
            assert not job.can_transition_to(target)
            with pytest.raises(AnalysisStateConflictError):
                job.transition_to(target, updated_at=datetime.now(UTC))


# --- Stage Lifecycle Tests ---


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (StageStatus.PENDING, StageStatus.QUEUED),
        (StageStatus.PENDING, StageStatus.RUNNING),
        (StageStatus.PENDING, StageStatus.SKIPPED),
        (StageStatus.PENDING, StageStatus.CANCELLED),
        (StageStatus.QUEUED, StageStatus.RUNNING),
        (StageStatus.QUEUED, StageStatus.SKIPPED),
        (StageStatus.QUEUED, StageStatus.CANCELLED),
        (StageStatus.RUNNING, StageStatus.COMPLETED),
        (StageStatus.RUNNING, StageStatus.FAILED),
        (StageStatus.RUNNING, StageStatus.CANCELLED),
    ],
)
def test_valid_stage_transitions(source: StageStatus, target: StageStatus) -> None:
    stage = _create_sample_stage(status=source)
    assert (
        stage.can_stage_transition(target)
        if hasattr(stage, "can_stage_transition")
        else stage.can_transition_to(target)
    )

    now = datetime.now(UTC)
    updated = stage.transition_to(
        target, updated_at=now, processed_items=5, total_items=10
    )

    assert updated.status == target
    assert updated.version == stage.version + 1
    assert updated.processed_items == 5


def test_terminal_stage_cannot_transition() -> None:
    for status in TERMINAL_STAGE_STATES:
        stage = _create_sample_stage(status=status)
        assert stage.is_terminal is True
        for target in StageStatus:
            assert not stage.can_transition_to(target)
            with pytest.raises(AnalysisStateConflictError):
                stage.transition_to(target, updated_at=datetime.now(UTC))
