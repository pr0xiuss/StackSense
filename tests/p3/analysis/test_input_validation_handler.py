"""Production input-validation stage coverage."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from backend.platform.analysis.application.registry import InputValidationStageHandler
from backend.platform.errors import AnalysisConfigurationError


def _context(*, total_files: int = 1) -> Mock:
    analysis_id = uuid4()
    project_id = uuid4()
    context = Mock()
    context.analysis_id = analysis_id
    context.project_id = project_id
    context.input = SimpleNamespace(
        analysis_id=analysis_id,
        project_id=project_id,
        total_files=total_files,
        total_bytes=10,
        artifact_catalog=SimpleNamespace(total_files=1, total_bytes=10),
    )
    return context


def test_input_validation_handler_completes_for_matching_immutable_input() -> None:
    context = _context()

    result = InputValidationStageHandler().execute(context)

    assert result.stage_name == "input_validation"
    assert result.status.value == "completed"
    assert (result.processed_items, result.total_items) == (1, 1)
    context.check_cancellation.assert_called_once_with()
    context.report_progress.assert_called_once_with(
        1, 1, "Validated immutable analysis input."
    )


def test_input_validation_handler_rejects_manifest_count_mismatch() -> None:
    context = _context(total_files=2)

    with pytest.raises(AnalysisConfigurationError, match="artifact count"):
        InputValidationStageHandler().execute(context)
