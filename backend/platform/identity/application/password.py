"""Password hasher contract."""

from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    """Contract for password hashing and verification."""

    @abstractmethod
    def hash(self, password: str) -> str:
        """Hash a plaintext password according to security policy."""
        ...

    @abstractmethod
    def verify(self, password: str, password_hash: str) -> bool:
        """Verify a plaintext password against a stored password hash."""
        ...

    @abstractmethod
    def validate(self, password: str) -> None:
        """Validate password against length and security policies."""
        ...
