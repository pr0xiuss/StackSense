"""Storage integration tests for LocalStorageService."""

import io
from pathlib import Path

import pytest

from backend.platform.errors import StorageOperationError
from backend.platform.ingestion.infra.storage.local_storage import (
    LocalStorageService,
)


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorageService:
    """Provide a LocalStorageService initialized in a temporary directory."""
    return LocalStorageService(tmp_path / "storage_root")


def test_put_bytes_and_get(storage: LocalStorageService) -> None:
    """Store raw bytes and read them back."""
    key = "artifacts/rev-1/src/main.py"
    data = b"print('hello world')\n"

    canonical_key = storage.put(key, data)
    assert canonical_key == key
    assert storage.exists(key) is True

    with storage.get(key) as stream:
        content = stream.read()
        assert content == data


def test_put_file_stream_and_get(storage: LocalStorageService) -> None:
    """Store data from a binary stream and read it back."""
    key = "artifacts/rev-1/docs/README.md"
    data = b"# Documentation\nSample content."
    stream = io.BytesIO(data)

    canonical_key = storage.put(key, stream)
    assert canonical_key == key
    assert storage.exists(key) is True

    with storage.get(key) as result_stream:
        assert result_stream.read() == data


def test_get_non_existent_key_raises_error(
    storage: LocalStorageService,
) -> None:
    """Verify reading a non-existent key raises StorageOperationError."""
    assert storage.exists("does/not/exist.txt") is False
    with pytest.raises(StorageOperationError) as exc_info:
        storage.get("does/not/exist.txt")
    assert "Object not found" in str(exc_info.value)


def test_delete_existing_key(storage: LocalStorageService) -> None:
    """Verify deleting a key removes the file and exists() returns False."""
    key = "temp/to_delete.txt"
    storage.put(key, b"to be removed")
    assert storage.exists(key) is True

    storage.delete(key)
    assert storage.exists(key) is False

    # Deleting a non-existent key should not raise an error
    storage.delete(key)


def test_delete_prefix(storage: LocalStorageService) -> None:
    """Verify deleting a directory prefix removes only items under that prefix."""
    storage.put("rev-1/file1.py", b"file1")
    storage.put("rev-1/nested/file2.py", b"file2")
    storage.put("rev-2/file1.py", b"file1-rev2")

    assert storage.exists("rev-1/file1.py") is True
    assert storage.exists("rev-1/nested/file2.py") is True
    assert storage.exists("rev-2/file1.py") is True

    storage.delete_prefix("rev-1")

    assert storage.exists("rev-1/file1.py") is False
    assert storage.exists("rev-1/nested/file2.py") is False
    assert storage.exists("rev-2/file1.py") is True


def test_path_traversal_escapes_blocked(
    storage: LocalStorageService,
) -> None:
    """Verify path traversal attacks using '..' are blocked."""
    malicious_keys = [
        "../escape.txt",
        "../../etc/passwd",
        "foo/../../escape.txt",
        "..\\windows\\system32",
    ]

    for key in malicious_keys:
        with pytest.raises(StorageOperationError):
            storage.put(key, b"exploit")

        with pytest.raises(StorageOperationError):
            storage.get(key)

        assert storage.exists(key) is False

        with pytest.raises(StorageOperationError):
            storage.delete(key)

        with pytest.raises(StorageOperationError):
            storage.delete_prefix(key)


def test_empty_or_root_prefix_deletion_blocked(
    storage: LocalStorageService,
) -> None:
    """Verify empty or root prefix cannot be deleted."""
    with pytest.raises(StorageOperationError):
        storage.delete_prefix("")

    with pytest.raises(StorageOperationError):
        storage.delete_prefix("/")

    with pytest.raises(StorageOperationError):
        storage.delete_prefix("///")
