"""Project application dependency for the current user."""

from fastapi import Depends

from backend.platform.identity.application.current_user import (
    CurrentUserProvider,
)
from backend.platform.identity.domain.user import User


def get_current_user_provider() -> CurrentUserProvider:
    """Provide the current-user provider."""
    raise NotImplementedError(
        "Authentication integration is required for current-user resolution."
    )


def get_current_user(
    provider: CurrentUserProvider = Depends(
        get_current_user_provider,
    ),
) -> User:
    """Resolve the authenticated user for the current request."""
    return provider.get_current_user()
