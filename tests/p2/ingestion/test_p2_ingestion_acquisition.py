"""Acquisition handler unit tests and security defenses."""

import io
import tarfile
import zipfile
from pathlib import Path

import httpx
import pytest

from backend.platform.errors import (
    GitHubAcquisitionError,
    GitHubRepositoryNotFoundError,
    InvalidGitHubRefError,
    ServerPathNotAllowedError,
    ServerPathNotFoundError,
    SourceValidationError,
    UnsupportedArchiveFormatError,
)
from backend.platform.ingestion.infra.acquisition.archive_handler import (
    ArchiveAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.directory_handler import (
    LocalDirectoryAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.github_handler import (
    GitHubAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.server_path_handler import (
    ServerPathAcquisitionHandler,
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


def _create_tar_file(
    tar_path: Path, entries: dict[str, bytes], mode: str = "w"
) -> Path:
    """Helper to create a tar or tar.gz archive with specified entries."""
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, mode) as tf:
        for name, data in entries.items():
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            ti.mtime = 1700000000
            tf.addfile(ti, io.BytesIO(data))
    return tar_path


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
    assert handler.can_handle("server_path") is True
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


# --- New Batch 2 Tests ---


def test_tar_acquisition_valid(tmp_path: Path) -> None:
    """Test extracting uncompressed .tar archive."""
    archive_path = tmp_path / "valid.tar"
    entries = {
        "src/app.py": b"print('tar app')\n",
        "README.md": b"# Tar Repo\n",
    }
    _create_tar_file(archive_path, entries, mode="w")

    handler = ArchiveAcquisitionHandler()
    assert handler.can_handle("archive") is True
    assert handler.can_handle("zip") is True

    temp_root = tmp_path / "extract_work"
    result = handler.acquire(
        str(archive_path),
        revision_identifier="v1.0-tar",
        temp_root=temp_root,
    )

    assert result.revision_identifier == "v1.0-tar"
    assert len(result.source_hash) == 64
    assert (result.root_path / "src" / "app.py").is_file()
    assert (result.root_path / "README.md").is_file()
    result.cleanup()
    assert not temp_root.exists()


def test_tar_gz_acquisition_valid(tmp_path: Path) -> None:
    """Test extracting compressed .tar.gz and .tgz archives."""
    for ext in (".tar.gz", ".tgz"):
        archive_path = tmp_path / f"valid{ext}"
        entries = {
            "pkg/module.py": b"x = 42\n",
            "docs/index.md": b"# Docs\n",
        }
        _create_tar_file(archive_path, entries, mode="w:gz")

        handler = ArchiveAcquisitionHandler()
        temp_root = tmp_path / f"extract_{ext.replace('.', '_')}"
        result = handler.acquire(
            str(archive_path),
            revision_identifier=None,
            temp_root=temp_root,
        )

        assert (result.root_path / "pkg" / "module.py").is_file()
        assert (result.root_path / "docs" / "index.md").is_file()
        assert len(result.source_hash) == 64
        result.cleanup()


def test_tar_path_traversal_blocked(tmp_path: Path) -> None:
    """Test that path traversal attempts in tar entries are rejected."""
    archive_path = tmp_path / "traversal.tar"
    entries = {
        "../escaped_tar.txt": b"malicious",
    }
    _create_tar_file(archive_path, entries, mode="w")

    handler = ArchiveAcquisitionHandler()
    with pytest.raises(SourceValidationError) as exc:
        handler.acquire(
            str(archive_path),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )
    assert "Path traversal" in str(exc.value)


def test_tar_symlink_blocked(tmp_path: Path) -> None:
    """Test that symbolic links in tar archives are rejected."""
    archive_path = tmp_path / "symlink.tar"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w") as tf:
        ti = tarfile.TarInfo(name="link_to_passwd")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "/etc/passwd"
        tf.addfile(ti)

    handler = ArchiveAcquisitionHandler()
    with pytest.raises(SourceValidationError) as exc:
        handler.acquire(
            str(archive_path),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )
    assert "Symbolic and hard links" in str(exc.value)


def test_server_path_archive_allowed(tmp_path: Path) -> None:
    """Test ServerPathAcquisitionHandler extracting allowed staged archive."""
    staged_root = tmp_path / "staged"
    staged_root.mkdir()
    archive_path = staged_root / "repo.tar.gz"
    entries = {
        "main.py": b"print('server path')\n",
    }
    _create_tar_file(archive_path, entries, mode="w:gz")

    handler = ServerPathAcquisitionHandler(allowed_roots=[str(staged_root)])
    assert handler.can_handle("server_path") is True

    temp_root = tmp_path / "work"
    result = handler.acquire(
        str(archive_path),
        revision_identifier="rev-server",
        temp_root=temp_root,
    )
    assert result.revision_identifier == "rev-server"
    assert (result.root_path / "main.py").is_file()
    result.cleanup()


def test_server_path_directory_allowed(tmp_path: Path) -> None:
    """Test ServerPathAcquisitionHandler reading allowed staged directory."""
    staged_root = tmp_path / "staged"
    staged_root.mkdir()
    repo_dir = staged_root / "my_project"
    repo_dir.mkdir()
    (repo_dir / "index.js").write_text("console.log('staged');")

    handler = ServerPathAcquisitionHandler(allowed_roots=[str(staged_root)])
    temp_root = tmp_path / "work"
    result = handler.acquire(
        str(repo_dir),
        revision_identifier=None,
        temp_root=temp_root,
    )
    assert result.root_path == repo_dir
    assert (result.root_path / "index.js").is_file()


def test_server_path_outside_allowed_root_rejected(tmp_path: Path) -> None:
    """Test ServerPathAcquisitionHandler blocks paths outside allowed roots."""
    staged_root = tmp_path / "staged"
    staged_root.mkdir()

    outside_dir = tmp_path / "secret_outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.tar.gz"
    _create_tar_file(secret_file, {"file.txt": b"secret"}, mode="w:gz")

    handler = ServerPathAcquisitionHandler(allowed_roots=[str(staged_root)])
    with pytest.raises(ServerPathNotAllowedError):
        handler.acquire(
            str(secret_file),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )


def test_server_path_non_existent(tmp_path: Path) -> None:
    """Test ServerPathAcquisitionHandler handles missing path inside allowed root."""
    staged_root = tmp_path / "staged"
    staged_root.mkdir()

    handler = ServerPathAcquisitionHandler(allowed_roots=[str(staged_root)])
    with pytest.raises(ServerPathNotFoundError):
        handler.acquire(
            str(staged_root / "missing.tar.gz"),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )


def test_server_path_unsupported_file_format(tmp_path: Path) -> None:
    """Test ServerPathAcquisitionHandler rejects non-archive regular files."""
    staged_root = tmp_path / "staged"
    staged_root.mkdir()
    txt_file = staged_root / "not_an_archive.txt"
    txt_file.write_text("just text")

    handler = ServerPathAcquisitionHandler(allowed_roots=[str(staged_root)])
    with pytest.raises(UnsupportedArchiveFormatError):
        handler.acquire(
            str(txt_file),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )


def test_server_path_symlink_escaping_jail(tmp_path: Path) -> None:
    """Test symlink in allowed root pointing outside allowed root is rejected."""
    staged_root = tmp_path / "staged"
    staged_root.mkdir()

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_archive = outside_dir / "outside.tar.gz"
    _create_tar_file(outside_archive, {"data.txt": b"outside"}, mode="w:gz")

    symlink_path = staged_root / "symlink_to_outside.tar.gz"
    symlink_path.symlink_to(outside_archive)

    handler = ServerPathAcquisitionHandler(allowed_roots=[str(staged_root)])
    with pytest.raises(ServerPathNotAllowedError):
        handler.acquire(
            str(symlink_path),
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )


def test_github_acquisition_success(tmp_path: Path) -> None:
    """Test successful public GitHub acquisition with container directory unwrapping."""
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tf:
        for name, data in [
            ("Hello-World-master/src/index.js", b"console.log('hi');\n"),
            ("Hello-World-master/README.md", b"# Hello World\n"),
        ]:
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            ti.mtime = 1700000000
            tf.addfile(ti, io.BytesIO(data))
    tar_bytes = tar_buffer.getvalue()

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        assert (
            str(request.url)
            == "https://codeload.github.com/octocat/Hello-World/tar.gz/master"
        )
        assert request.headers.get("User-Agent") == "StackSense-Ingestion/0.1.0"
        return httpx.Response(200, content=tar_bytes, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport_handler))

    handler = GitHubAcquisitionHandler(http_client=mock_client)
    assert handler.can_handle("github") is True

    temp_root = tmp_path / "work"
    result = handler.acquire(
        source_reference="https://github.com/octocat/Hello-World@master",
        revision_identifier=None,
        temp_root=temp_root,
    )

    # Unwrapping ensures files are accessible directly at root
    assert (result.root_path / "src" / "index.js").is_file()
    assert (result.root_path / "README.md").is_file()
    assert result.revision_identifier == "master"
    assert len(result.source_hash) == 64
    assert result.total_source_bytes == len(tar_bytes)
    result.cleanup()
    assert not temp_root.exists()


def test_github_acquisition_default_ref_head(tmp_path: Path) -> None:
    """Test GitHub acquisition defaults to HEAD when ref is omitted."""
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tf:
        ti = tarfile.TarInfo(name="repo-HEAD/README.md")
        ti.size = 5
        ti.mtime = 1700000000
        tf.addfile(ti, io.BytesIO(b"hello"))
    tar_bytes = tar_buffer.getvalue()

    requested_urls: list[str] = []

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, content=tar_bytes, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport_handler))
    handler = GitHubAcquisitionHandler(http_client=mock_client)

    result = handler.acquire(
        source_reference="https://github.com/octocat/Hello-World",
        revision_identifier=None,
        temp_root=tmp_path / "work",
    )
    assert (
        requested_urls[0]
        == "https://codeload.github.com/octocat/Hello-World/tar.gz/HEAD"
    )
    assert (result.root_path / "README.md").is_file()
    result.cleanup()


def test_github_acquisition_not_found(tmp_path: Path) -> None:
    """Test 404 from GitHub maps to GitHubRepositoryNotFoundError."""

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport_handler))
    handler = GitHubAcquisitionHandler(http_client=mock_client)

    with pytest.raises(GitHubRepositoryNotFoundError):
        handler.acquire(
            source_reference="https://github.com/octocat/private-repo",
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )


def test_github_acquisition_rate_limited(tmp_path: Path) -> None:
    """Test 429 from GitHub maps to GitHubAcquisitionError."""

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport_handler))
    handler = GitHubAcquisitionHandler(http_client=mock_client)

    with pytest.raises(GitHubAcquisitionError) as exc:
        handler.acquire(
            source_reference="https://github.com/octocat/Hello-World",
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )
    from backend.platform.errors import GitHubRateLimitExceededError

    assert isinstance(exc.value, GitHubRateLimitExceededError)
    assert "not found or access denied" in str(exc.value).lower()


def test_github_acquisition_timeout(tmp_path: Path) -> None:
    """Test network timeout maps to GitHubAcquisitionError."""

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Network timeout")

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport_handler))
    handler = GitHubAcquisitionHandler(http_client=mock_client)

    with pytest.raises(GitHubAcquisitionError) as exc:
        handler.acquire(
            source_reference="https://github.com/octocat/Hello-World",
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )
    assert "timed out" in str(exc.value)


def test_github_acquisition_invalid_ref_blocked(tmp_path: Path) -> None:
    """Test that invalid ref with traversal is rejected before network fetch."""
    handler = GitHubAcquisitionHandler()
    with pytest.raises(InvalidGitHubRefError):
        handler.acquire(
            source_reference="https://github.com/octocat/Hello-World@../bad",
            revision_identifier=None,
            temp_root=tmp_path / "work",
        )


def test_zip_archive_acquisition_handler_legacy_alias(tmp_path: Path) -> None:
    """Test ZipArchiveAcquisitionHandler legacy subclass handles zip and extracts."""
    handler = ZipArchiveAcquisitionHandler()
    assert handler.can_handle("zip") is True
    assert handler.can_handle("archive") is True
    assert handler.can_handle("github") is False

    zip_path = tmp_path / "legacy.zip"
    _create_zip_file(zip_path, {"test.py": b"print('hello')\n"})

    res = handler.acquire(
        str(zip_path),
        revision_identifier="v1.0",
        temp_root=tmp_path / "work",
    )
    assert (res.root_path / "test.py").exists()
    assert res.revision_identifier == "v1.0"
    if res.cleanup_fn:
        res.cleanup_fn()


def test_parse_github_url_coordinates() -> None:
    """Test parse_github_url returns canonical URL, owner, and repo."""
    from backend.platform.ingestion.domain import parse_github_url

    canonical, owner, repo = parse_github_url("https://github.com/torvalds/linux.git")
    assert canonical == "https://github.com/torvalds/linux"
    assert owner == "torvalds"
    assert repo == "linux"
