"""User repository persistence contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.identity.domain.credential import UserCredential
from backend.platform.identity.domain.user import User


class UserRepository(ABC):
    """Persistence contract for User entities and associated credentials."""

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> User | None:
        """Retrieve a user by their unique identifier."""
        ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Retrieve a user by their email address."""
        ...

    @abstractmethod
    def get_credential_by_user_id(self, user_id: UUID) -> UserCredential | None:
        """Retrieve a user's credential by user identifier."""
        ...

    @abstractmethod
    def save(self, user: User, credential: UserCredential | None = None) -> User:
        """Persist a new user and optional initial credential."""
        ...

    @abstractmethod
    def update(self, user: User) -> User:
        """Update an existing user's state."""
        ...
