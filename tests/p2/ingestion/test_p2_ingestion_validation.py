"""Validation pipeline unit tests."""

from pathlib import Path

import pytest

from backend.platform.errors import SourceValidationError
from backend.platform.ingestion.application.validator import (
    SourceValidator,
)


def test_validator_valid_directory(tmp_path: Path) -> None:
    """Test validating a normal repository directory structure."""
    repo_root = tmp_path / "my_repo"
    (repo_root / "src" / "pkg").mkdir(parents=True)
    (repo_root / "src" / "pkg" / "mod.py").write_text("x = 1\n")
    (repo_root / "README.md").write_text("# Readme\n")

    validator = SourceValidator()
    validated = validator.validate(repo_root)

    assert validated.total_files == 2
    assert validated.total_bytes > 0
    paths = {f.relative_path for f in validated.files}
    assert paths == {"src/pkg/mod.py", "README.md"}


def test_validator_non_directory_target(tmp_path: Path) -> None:
    """Test validator rejects non-directory targets."""
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("content")

    validator = SourceValidator()
    with pytest.raises(SourceValidationError):
        validator.validate(file_path)


def test_validator_directory_depth_exceeded(tmp_path: Path) -> None:
    """Test validator rejects directory trees deeper than MAX_DIRECTORY_DEPTH."""
    deep_path = tmp_path / "deep"
    for i in range(105):
        deep_path = deep_path / f"d{i}"
    deep_path.mkdir(parents=True)
    (deep_path / "leaf.txt").write_text("too deep")

    validator = SourceValidator()
    with pytest.raises(SourceValidationError) as exc:
        validator.validate(tmp_path / "deep")
    assert "Directory depth" in str(exc.value)


def test_validator_path_length_exceeded(tmp_path: Path) -> None:
    """Test validator rejects paths longer than MAX_PATH_LENGTH."""
    repo = tmp_path / "long_path_repo"
    # Create segment of 100 chars repeated
    dir_part = "a" * 100
    curr = repo
    for _ in range(42):  # 42 * 100 > 4096
        curr = curr / dir_part
    curr.mkdir(parents=True)
    (curr / "file.txt").write_text("data")

    validator = SourceValidator()
    with pytest.raises(SourceValidationError) as exc:
        validator.validate(repo)
    assert "Path length" in str(exc.value)
