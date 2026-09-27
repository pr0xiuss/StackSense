"""Current authenticated user application contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.identity.domain.user import User


class CurrentUserProvider(ABC):
    """Provide the user associated with the current request."""

    @abstractmethod
    def get_current_user(self) -> User:
        """Return the authenticated user for the current request."""
        ...


class StaticCurrentUserProvider(CurrentUserProvider):
    """Temporary development provider for the current user."""

    def __init__(self, user_id: UUID) -> None:
        self._user = User(
            id=user_id,
            email=f"user-{user_id}@stacksense.local",
            is_active=True,
        )

    def get_current_user(self) -> User:
        """Return the configured development user."""
        return self._user


class AuthenticatedCurrentUserProvider(CurrentUserProvider):
    """Current-user provider holding the authenticated user from a validated token."""

    def __init__(self, user: User) -> None:
        self._user = user

    def get_current_user(self) -> User:
        """Return the authenticated user."""
        return self._user
