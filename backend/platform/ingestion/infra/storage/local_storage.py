"""Local filesystem implementation of the StorageService contract."""

import shutil
from pathlib import Path
from typing import BinaryIO

from backend.platform.errors import StorageOperationError
from backend.platform.ingestion.application.storage import StorageService


class LocalStorageService(StorageService):
    """Filesystem-backed implementation of StorageService.

    Operates strictly within an isolated root directory, verifying that all
    read, write, and delete operations remain contained.
    """

    def __init__(self, root_path: Path | str) -> None:
        self._root = Path(root_path).resolve()
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageOperationError(
                f"Failed to initialize storage root at {self._root}: {exc}"
            ) from exc

    @property
    def root(self) -> Path:
        """Return the resolved storage root path."""
        return self._root

    def _resolve_key(self, key: str) -> Path:
        """Normalize key and verify target path does not escape storage root."""
        clean_key = key.replace("\\", "/").strip("/")
        if not clean_key or ".." in clean_key.split("/"):
            raise StorageOperationError(f"Invalid storage key: {key}")

        target = (self._root / clean_key).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as exc:
            raise StorageOperationError(
                f"Storage key escapes storage root: {key}"
            ) from exc

        return target

    def put(self, key: str, data: BinaryIO | bytes) -> str:
        """Store content under key and return the canonical key."""
        target = self._resolve_key(key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(data, bytes):
                target.write_bytes(data)
            else:
                with open(target, "wb") as destination:
                    shutil.copyfileobj(data, destination)
            return key.replace("\\", "/").strip("/")
        except OSError as exc:
            raise StorageOperationError(
                f"Failed to write storage key {key}: {exc}"
            ) from exc

    def get(self, key: str) -> BinaryIO:
        """Retrieve a binary stream for key."""
        target = self._resolve_key(key)
        if not target.is_file():
            raise StorageOperationError(f"Object not found at storage key: {key}")

        try:
            return open(target, "rb")
        except OSError as exc:
            raise StorageOperationError(
                f"Failed to read storage key {key}: {exc}"
            ) from exc

    def exists(self, key: str) -> bool:
        """Return True if an object exists at key, False otherwise."""
        try:
            target = self._resolve_key(key)
            return target.is_file()
        except StorageOperationError:
            return False

    def delete(self, key: str) -> None:
        """Delete the object at key if it exists."""
        target = self._resolve_key(key)
        try:
            if target.is_file():
                target.unlink()
        except OSError as exc:
            raise StorageOperationError(
                f"Failed to delete storage key {key}: {exc}"
            ) from exc

    def delete_prefix(self, prefix: str) -> None:
        """Delete all objects sharing the given key prefix."""
        clean_prefix = prefix.replace("\\", "/").strip("/")
        if not clean_prefix:
            raise StorageOperationError(
                "Cannot delete empty storage prefix (root deletion blocked)"
            )

        target = self._resolve_key(clean_prefix)
        try:
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            elif target.is_file():
                target.unlink(missing_ok=True)
            else:
                # Target path does not exist directly, but might match a prefix pattern
                # within its parent directory
                parent = target.parent
                if parent.is_dir():
                    prefix_str = str(target)
                    for item in parent.iterdir():
                        if str(item).startswith(prefix_str):
                            if item.is_dir():
                                shutil.rmtree(item, ignore_errors=True)
                            else:
                                item.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageOperationError(
                f"Failed to delete storage prefix {prefix}: {exc}"
            ) from exc
