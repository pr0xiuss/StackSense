"""Dependency providers for the Identity application layer."""

from uuid import UUID

from fastapi import Depends

from backend.platform.identity.application.current_user import (
    CurrentUserProvider,
    StaticCurrentUserProvider,
)
from backend.platform.identity.domain.user import User


def get_current_user_provider() -> CurrentUserProvider:
    """Provide the current-user provider for the application."""
    return StaticCurrentUserProvider(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
    )


def get_current_user(
    provider: CurrentUserProvider = Depends(
        get_current_user_provider,
    ),
) -> User:
    """Return the authenticated user for the current request."""
    return provider.get_current_user()
