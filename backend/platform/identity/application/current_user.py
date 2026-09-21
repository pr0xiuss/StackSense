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
        self._user = User(id=user_id)

    def get_current_user(self) -> User:
        """Return the configured development user."""
        return self._user
