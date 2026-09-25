"""Acquisition handler unit tests and security defenses."""

import zipfile
from pathlib import Path

import pytest

from backend.platform.errors import SourceValidationError
from backend.platform.ingestion.infra.acquisition.directory_handler import (
    LocalDirectoryAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.zip_handler import (
    ZipArchiveAcquisitionHandler,
)


def _create_zip_file(zip_path: Path, entries: dict[str, bytes]) -> Path:
    """Helper to create a zip file with specified path entries and content."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return zip_path


def test_zip_acquisition_valid(tmp_path: Path) -> None:
    """Test extracting a valid zip archive."""
    archive_path = tmp_path / "valid.zip"
    entries = {
        "src/main.py": b"print('hello')\n",
        "README.md": b"# Sample Repo\n",
    }
    _create_zip_file(archive_path, entries)

    handler = ZipArchiveAcquisitionHandler()
    assert handler.can_handle("archive") is True
    assert handler.can_handle("zip") is True
    assert handler.can_handle("directory") is False

    temp_root = tmp_path / "extract_work"
    result = handler.acquire(
        str(archive_path),
        revision_identifier="v1.0",
        temp_root=temp_root,
    )

    assert result.revision_identifier == "v1.0"
    assert len(result.source_hash) == 64
    assert (result.root_path / "src" / "main.py").is_file()
    assert (result.root_path / "README.md").is_file()

    result.cleanup()
    assert not temp_root.exists()


def test_zip_path_traversal_blocked(tmp_path: Path) -> None:
    """Test that path traversal attempts in zip entries are rejected."""
    archive_path = tmp_path / "traversal.zip"
    entries = {
        "../escaped.txt": b"malicious",
    }
    _create_zip_file(archive_path, entries)

    handler = ZipArchiveAcquisitionHandler()
    with pytest.raises(SourceValidationError) as exc:
        handler.acquire(
            str(archive_path),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )
    assert "Path traversal" in str(exc.value)


def test_zip_bomb_compression_ratio_defense(tmp_path: Path) -> None:
    """Test rejection of zip bomb with massive compression ratio."""
    archive_path = tmp_path / "bomb.zip"
    # Create 2MB of zeroes that compress down to near zero bytes
    huge_data = b"0" * (2 * 1024 * 1024)
    _create_zip_file(archive_path, {"bomb.txt": huge_data})

    handler = ZipArchiveAcquisitionHandler()
    with pytest.raises(SourceValidationError) as exc:
        handler.acquire(
            str(archive_path),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )
    assert "High compression ratio" in str(exc.value)


def test_zip_nested_archives_depth_defense(tmp_path: Path) -> None:
    """Test rejection of deeply nested archive files."""
    archive_path = tmp_path / "nested.zip"
    entries = {
        "level1.zip/level2.tar/level3.gz": b"deeply nested",
    }
    _create_zip_file(archive_path, entries)

    handler = ZipArchiveAcquisitionHandler()
    with pytest.raises(SourceValidationError) as exc:
        handler.acquire(
            str(archive_path),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )
    assert "Archive nesting depth exceeds limit" in str(exc.value)


def test_zip_non_existent_file(tmp_path: Path) -> None:
    """Test acquisition fails cleanly if archive path does not exist."""
    handler = ZipArchiveAcquisitionHandler()
    with pytest.raises(SourceValidationError):
        handler.acquire(
            str(tmp_path / "missing.zip"),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )


def test_zip_invalid_file_format(tmp_path: Path) -> None:
    """Test acquisition fails cleanly on invalid zip format."""
    fake_zip = tmp_path / "corrupt.zip"
    fake_zip.write_bytes(b"not a valid zip file")

    handler = ZipArchiveAcquisitionHandler()
    with pytest.raises(SourceValidationError):
        handler.acquire(
            str(fake_zip),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )


def test_local_directory_acquisition(tmp_path: Path) -> None:
    """Test acquisition from a local directory source."""
    source_dir = tmp_path / "local_repo"
    source_dir.mkdir()
    (source_dir / "index.ts").write_text("console.log('hi');")
    (source_dir / "package.json").write_text("{}")

    handler = LocalDirectoryAcquisitionHandler()
    assert handler.can_handle("directory") is True
    assert handler.can_handle("archive") is False

    result = handler.acquire(
        str(source_dir),
        revision_identifier=None,
        temp_root=tmp_path / "work",
    )

    assert result.root_path == source_dir
    assert len(result.source_hash) == 64
    assert result.total_source_bytes > 0
    assert (result.root_path / "index.ts").is_file()
