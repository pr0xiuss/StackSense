"""Focused regression tests for M1 security and production boundaries."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.platform.analysis.application.dependencies import (
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.analysis.application.dto import CreateAnalysisRequest
from backend.platform.analysis.domain.constants import MAX_READ_BYTES_LIMIT
from backend.platform.config import Settings
from backend.platform.errors import (
    AnalysisAccessDeniedError,
    AnalysisInputError,
    AuthenticationRequiredError,
)


def test_internal_analysis_api_requires_service_authentication() -> None:
    with pytest.raises(AuthenticationRequiredError):
        get_delegated_context(
            settings=Settings(),
            x_service_token=None,
            x_actor_id=None,
            x_actor_role=None,
            x_project_id=None,
            x_correlation_id=None,
        )


def test_delegated_context_requires_complete_valid_scope() -> None:
    settings = Settings()
    secret = settings.internal_api_secret_key.get_secret_value()
    with pytest.raises(AnalysisInputError):
        get_delegated_context(
            settings=settings,
            x_service_token=secret,
            x_actor_id=str(uuid4()),
            x_actor_role="ADMIN",
            x_project_id=None,
            x_correlation_id=None,
        )


def test_delegated_project_cannot_be_substituted() -> None:
    settings = Settings()
    project_id = uuid4()
    context = get_delegated_context(
        settings=settings,
        x_service_token=settings.internal_api_secret_key.get_secret_value(),
        x_actor_id=str(uuid4()),
        x_actor_role="DEVELOPER",
        x_project_id=str(project_id),
        x_correlation_id=None,
    )
    assert require_delegated_project(context, project_id) == project_id
    with pytest.raises(AnalysisAccessDeniedError):
        require_delegated_project(context, uuid4())


def test_analysis_request_enforces_resource_limits() -> None:
    with pytest.raises(ValidationError):
        CreateAnalysisRequest(
            project_id=uuid4(),
            repository_id=uuid4(),
            revision_id=uuid4(),
            max_file_size_bytes=MAX_READ_BYTES_LIMIT + 1,
        )
    with pytest.raises(ValidationError):
        CreateAnalysisRequest(
            project_id=uuid4(),
            repository_id=uuid4(),
            revision_id=uuid4(),
            timeout_seconds=0,
        )


def test_default_production_service_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production")
