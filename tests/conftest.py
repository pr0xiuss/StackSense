"""Shared pytest configuration for StackSense tests."""

from collections.abc import Callable, Generator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.platform.dependency_injection import get_database
from backend.platform.identity.application.current_user import (
    StaticCurrentUserProvider,
)
from backend.platform.identity.application.dependencies import (
    get_current_user_provider,
)
from backend.platform.identity.domain.user import User
from backend.platform.identity.infra.user_repo import SqlAlchemyUserRepository

DETERMINISTIC_TEST_USERS = [
    UUID("00000000-0000-0000-0000-000000000001"),
    UUID("00000000-0000-0000-0000-000000000002"),
    UUID("00000000-0000-0000-0000-000000000003"),
]


def ensure_test_user(user_id: UUID | str) -> User:
    """Explicit test helper to persist a User via the repository contract."""
    uid = UUID(str(user_id))
    database = get_database()
    session_gen = database.session()
    session = next(session_gen)
    try:
        repo = SqlAlchemyUserRepository(session)
        existing = repo.get_by_id(uid)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        user = repo.save(
            User(
                id=uid,
                email=f"test-user-{uid}@stacksense.local",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        return user
    finally:
        session_gen.close()


@pytest.fixture
def client() -> Generator[TestClient]:
    """Provide a test client for the StackSense API with deterministic test users."""
    for uid in DETERMINISTIC_TEST_USERS:
        ensure_test_user(uid)
    app.dependency_overrides[get_current_user_provider] = (
        lambda: StaticCurrentUserProvider(DETERMINISTIC_TEST_USERS[0])
    )
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user_provider, None)


@pytest.fixture
def unauthenticated_client() -> TestClient:
    """Provide a test client without any current user overrides or authentication."""
    return TestClient(app)


@pytest.fixture
def set_current_user() -> Generator[Callable[[UUID], None]]:
    """Override current authenticated user for a test and ensure user is persisted."""

    def _set_current_user(user_id: UUID) -> None:
        ensure_test_user(user_id)
        app.dependency_overrides[get_current_user_provider] = (
            lambda: StaticCurrentUserProvider(user_id)
        )

    yield _set_current_user

    app.dependency_overrides.pop(
        get_current_user_provider,
        None,
    )
