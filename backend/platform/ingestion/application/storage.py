"""Storage service contract."""

from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageService(ABC):
    """Abstract interface defining external content storage operations.

    Decouples the domain/application layer from filesystem, S3, or other
    concrete storage provider mechanics.
    """

    @abstractmethod
    def put(self, key: str, data: BinaryIO | bytes) -> str:
        """Store content under key and return the stored key."""
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str) -> BinaryIO:
        """Retrieve a binary stream for key.

        Raises StorageOperationError if key does not exist.
        """
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if an object exists at key, False otherwise."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete the object at key if it exists."""
        raise NotImplementedError

    @abstractmethod
    def delete_prefix(self, prefix: str) -> None:
        """Delete all objects sharing the given key prefix (compensating cleanup)."""
        raise NotImplementedError
