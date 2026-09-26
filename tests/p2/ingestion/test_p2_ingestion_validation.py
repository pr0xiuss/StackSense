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
    """Test validator rejects paths longer than configured max_path_length."""
    repo = tmp_path / "long_path_repo"
    sub_dir = repo / ("sub_" + "a" * 40)
    sub_dir.mkdir(parents=True)
    file_path = sub_dir / ("file_" + "b" * 40 + ".txt")
    file_path.write_text("data")

    # Relative path is ~89 characters, exceeding configured limit of 80
    validator = SourceValidator(max_path_length=80)
    with pytest.raises(SourceValidationError) as exc:
        validator.validate(repo)
    assert "Path length" in str(exc.value)
    assert "exceeds limit of 80" in str(exc.value)


def test_validator_default_max_path_length_exceeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test validator rejects paths exceeding the default MAX_PATH_LENGTH (4096)."""
    repo = tmp_path / "default_limit_repo"
    repo.mkdir(parents=True)
    real_file = repo / "test.txt"
    real_file.write_text("hello")

    # POSIX Linux enforces PATH_MAX=4096 at the kernel level for actual
    # filesystem syscalls. We verify the validator's default MAX_PATH_LENGTH
    # limit (4096) by simulating a relative path exceeding 4096 characters
    # without triggering kernel ENAMETOOLONG.
    orig_relative_to = Path.relative_to
    long_rel_path = Path("a" * 4097)

    def fake_relative_to(self: Path, other: Path) -> Path:
        if self == real_file:
            return long_rel_path
        return orig_relative_to(self, other)

    monkeypatch.setattr(Path, "relative_to", fake_relative_to)

    validator = SourceValidator()  # Uses default MAX_PATH_LENGTH (4096)
    with pytest.raises(SourceValidationError) as exc:
        validator.validate(repo)
    assert "Path length (4097) exceeds limit of 4096" in str(exc.value)


def test_validator_file_count_exceeded(tmp_path: Path) -> None:
    """Test validator rejects repositories exceeding max_file_count."""
    repo = tmp_path / "file_count_repo"
    repo.mkdir(parents=True)
    for i in range(5):
        (repo / f"file_{i}.txt").write_text("x")

    validator = SourceValidator(max_file_count=3)
    with pytest.raises(SourceValidationError) as exc:
        validator.validate(repo)
    assert "File count exceeds maximum" in str(exc.value)


def test_validator_extracted_size_exceeded(tmp_path: Path) -> None:
    """Test validator rejects repositories exceeding max_extracted_size_bytes."""
    repo = tmp_path / "size_repo"
    repo.mkdir(parents=True)
    (repo / "large.bin").write_bytes(b"0" * 200)

    validator = SourceValidator(max_extracted_size_bytes=100)
    with pytest.raises(SourceValidationError) as exc:
        validator.validate(repo)
    assert "Total extracted size (200 bytes) exceeds maximum" in str(exc.value)


def test_validator_os_error_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test validator converts unexpected OSError into SourceValidationError."""
    repo = tmp_path / "os_error_repo"
    repo.mkdir(parents=True)
    file_path = repo / "file.txt"
    file_path.write_text("data")

    def mock_stat(self: Path, *args: object, **kwargs: object) -> object:
        raise OSError("Simulated disk read error")

    monkeypatch.setattr(Path, "stat", mock_stat)

    validator = SourceValidator()
    with pytest.raises(SourceValidationError) as exc:
        validator.validate(repo)
    assert "Filesystem access error" in str(exc.value)
