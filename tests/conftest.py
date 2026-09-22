"""Shared pytest configuration for StackSense tests."""

from collections.abc import Callable, Generator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.platform.identity.application.current_user import (
    StaticCurrentUserProvider,
)
from backend.platform.identity.application.dependencies import (
    get_current_user_provider,
)


@pytest.fixture
def client() -> TestClient:
    """Provide a test client for the StackSense API."""
    return TestClient(app)


@pytest.fixture
def set_current_user() -> Generator[Callable[[UUID], None]]:
    """Override the current authenticated user for a test."""

    def _set_current_user(user_id: UUID) -> None:
        app.dependency_overrides[get_current_user_provider] = (
            lambda: StaticCurrentUserProvider(user_id)
        )

    yield _set_current_user

    app.dependency_overrides.pop(
        get_current_user_provider,
        None,
    )
