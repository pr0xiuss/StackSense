"""End-to-end API integration tests for Ingestion endpoints."""

import io
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.platform.dependency_injection import get_database
from backend.platform.ingestion.domain.constants import IngestionStatus
from backend.platform.ingestion.domain.ingestion import Ingestion
from backend.platform.ingestion.infra.ingestion_repository import (
    SqlAlchemyIngestionRepository,
)


def _create_zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def _create_tar_bytes(files: dict[str, bytes], mode: str = "w:gz") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as tf:
        for name, data in files.items():
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            ti.mtime = 1700000000
            tf.addfile(ti, io.BytesIO(data))
    return buffer.getvalue()


def _setup_project_and_repo(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> tuple[str, str, UUID]:
    owner_id = uuid4()
    set_current_user(owner_id)

    proj_res = client.post(
        "/api/v1/projects",
        json={"name": f"API-Proj-{uuid4().hex[:6]}", "description": "Desc"},
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    repo_res = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": f"API-Repo-{uuid4().hex[:6]}", "description": "Repo"},
    )
    assert repo_res.status_code == 201
    repository_id = repo_res.json()["id"]

    return project_id, repository_id, owner_id


def test_trigger_ingestion_json_api_success(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
    tmp_path: Path,
) -> None:
    project_id, repository_id, owner_id = _setup_project_and_repo(
        client, set_current_user
    )

    zip_path = tmp_path / "source.zip"
    zip_bytes = _create_zip_bytes(
        {
            "src/index.ts": b"console.log('hi');\n",
            "package.json": b'{"name": "test"}\n',
        }
    )
    zip_path.write_bytes(zip_bytes)

    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/ingestions",
        json={
            "repository_id": repository_id,
            "source_type": "archive",
            "source_reference": str(zip_path),
            "revision_identifier": "v1.0.0",
        },
    )
    assert response.status_code == 201
    data = response.json()

    assert data["repository_id"] == repository_id
    assert data["project_id"] == project_id
    assert data["status"] == "completed"
    assert data["started_at"] is not None
    assert data["completed_at"] is not None
    assert data["error_code"] is None


def test_upload_and_ingest_multipart_api_success(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, repository_id, owner_id = _setup_project_and_repo(
        client, set_current_user
    )

    zip_bytes = _create_zip_bytes(
        {
            "main.py": b"print('hello world')\n",
            "README.md": b"# Uploaded Repo\n",
        }
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/ingestions/upload",
        files={"file": ("archive.zip", zip_bytes, "application/zip")},
        data={"revision_identifier": "v2.0.0"},
    )
    assert response.status_code == 201
    data = response.json()

    assert data["status"] == "completed"
    assert data["repository_id"] == repository_id

    # Check revisions
    rev_res = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/revisions"
    )
    assert rev_res.status_code == 200
    revisions = rev_res.json()
    assert len(revisions) >= 1
    rev = next(r for r in revisions if r["revision_identifier"] == "v2.0.0")
    assert rev["total_files"] == 2

    # Check artifacts
    art_res = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/revisions/{rev['id']}/artifacts"
    )
    assert art_res.status_code == 200
    artifacts = art_res.json()
    assert len(artifacts) == 2
    paths = {a["path"] for a in artifacts}
    assert paths == {"README.md", "main.py"}


def test_get_and_list_ingestions_api(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, repository_id, owner_id = _setup_project_and_repo(
        client, set_current_user
    )

    zip_bytes = _create_zip_bytes({"app.py": b"x=1\n"})
    upload_res = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/ingestions/upload",
        files={"file": ("test.zip", zip_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    ingestion_id = upload_res.json()["id"]

    # Get by ID
    get_res = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/ingestions/{ingestion_id}"
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == ingestion_id

    # List ingestions
    list_res = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/ingestions"
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


def test_get_and_list_revisions_api(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, repository_id, owner_id = _setup_project_and_repo(
        client, set_current_user
    )

    zip_bytes = _create_zip_bytes({"src/lib.rs": b"fn main() {}\n"})
    upload_res = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/ingestions/upload",
        files={"file": ("rust.zip", zip_bytes, "application/zip")},
        data={"revision_identifier": "rust-v1"},
    )
    assert upload_res.status_code == 201

    rev_list_res = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/revisions"
    )
    assert rev_list_res.status_code == 200
    revs = rev_list_res.json()
    rev_id = revs[0]["id"]

    get_rev_res = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/revisions/{rev_id}"
    )
    assert get_rev_res.status_code == 200
    assert get_rev_res.json()["revision_identifier"] == "rust-v1"


def test_active_ingestion_race_returns_409(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, repository_id, owner_id = _setup_project_and_repo(
        client, set_current_user
    )

    # Simulate an active job in the database
    database = get_database()
    session_gen = database.session()
    session = next(session_gen)
    try:
        from datetime import UTC, datetime

        repo = SqlAlchemyIngestionRepository(session)
        now = datetime.now(UTC)
        repo.save(
            Ingestion(
                id=uuid4(),
                project_id=UUID(project_id),
                repository_id=UUID(repository_id),
                source_type="archive",
                source_reference="s3://path.zip",
                status=IngestionStatus.PROCESSING,
                error_code=None,
                error_message=None,
                started_at=now,
                completed_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session_gen.close()

    # Attempt to trigger another ingestion
    zip_bytes = _create_zip_bytes({"file.py": b"1"})
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/ingestions/upload",
        files={"file": ("test.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "active_ingestion_exists"


def test_unauthorized_user_returns_403(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, repository_id, owner_id = _setup_project_and_repo(
        client, set_current_user
    )

    viewer_id = uuid4()
    # Grant viewer role
    client.post(
        f"/api/v1/projects/{project_id}/access",
        json={"user_id": str(viewer_id), "role": "VIEWER"},
    )

    set_current_user(viewer_id)
    zip_bytes = _create_zip_bytes({"test.py": b"1"})

    # Viewer cannot trigger ingestion
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/ingestions/upload",
        files={"file": ("test.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "project_access_denied"


def test_invalid_archive_upload_returns_422(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, repository_id, owner_id = _setup_project_and_repo(
        client, set_current_user
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository_id}/ingestions/upload",
        files={"file": ("corrupt.zip", b"not a zip", "application/zip")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "source_validation_failed"


def test_cross_project_isolation_api(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project1_id, repo1_id, owner1_id = _setup_project_and_repo(client, set_current_user)
    project2_id, repo2_id, owner2_id = _setup_project_and_repo(client, set_current_user)

    # Ingest into project 1
    set_current_user(owner1_id)
    zip_bytes = _create_zip_bytes({"p1.py": b"print('p1')\n"})
    upload_res = client.post(
        f"/api/v1/projects/{project1_id}/repositories/{repo1_id}/ingestions/upload",
        files={"file": ("p1.zip", zip_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    ingestion_id = upload_res.json()["id"]

    # Owner 2 tries to access Project 1's ingestion
    set_current_user(owner2_id)
    denied_res = client.get(
        f"/api/v1/projects/{project1_id}/repositories/{repo1_id}/ingestions/{ingestion_id}"
    )
    assert denied_res.status_code == 403
    assert denied_res.json()["error"]["code"] == "project_access_denied"

    # Owner 2 tries with Project 2 ID but repo 1 ID -> 404 RepositoryNotFoundError
    mismatch_res = client.get(
        f"/api/v1/projects/{project2_id}/repositories/{repo1_id}/ingestions/{ingestion_id}"
    )
    assert mismatch_res.status_code == 404
    assert mismatch_res.json()["error"]["code"] == "repository_not_found"


def test_duplicate_revision_identifier_rejected_with_409(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, repo_id, owner_id = _setup_project_and_repo(client, set_current_user)

    zip_bytes1 = _create_zip_bytes({"app.py": b"print('v1')\n"})
    res1 = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions/upload",
        files={"file": ("repo.zip", zip_bytes1, "application/zip")},
        data={"revision_identifier": "v1.0"},
    )
    assert res1.status_code == 201
    assert res1.json()["status"] == "completed"

    # Second upload with the exact same revision identifier must be rejected with 409
    zip_bytes2 = _create_zip_bytes({"app.py": b"print('v1 duplicate')\n"})
    res2 = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions/upload",
        files={"file": ("repo.zip", zip_bytes2, "application/zip")},
        data={"revision_identifier": "v1.0"},
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "revision_already_exists"


def test_upload_tar_gz_and_tgz_and_tar_api_success(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    """Test multipart upload with .tar.gz, .tgz, and .tar archives."""
    project_id, repo_id, _ = _setup_project_and_repo(client, set_current_user)

    # 1. Upload .tar.gz
    tar_gz_bytes = _create_tar_bytes(
        {"app.py": b"print('tar.gz')\n", "README.md": b"# TarGz\n"},
        mode="w:gz",
    )
    res_gz = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions/upload",
        files={"file": ("project.tar.gz", tar_gz_bytes, "application/gzip")},
        data={"revision_identifier": "rev-tar-gz"},
    )
    assert res_gz.status_code == 201
    assert res_gz.json()["status"] == "completed"

    # 2. Upload .tgz
    tgz_bytes = _create_tar_bytes(
        {"app.py": b"print('tgz')\n"},
        mode="w:gz",
    )
    res_tgz = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions/upload",
        files={"file": ("project.tgz", tgz_bytes, "application/gzip")},
        data={"revision_identifier": "rev-tgz"},
    )
    assert res_tgz.status_code == 201
    assert res_tgz.json()["status"] == "completed"

    # 3. Upload .tar
    tar_bytes = _create_tar_bytes(
        {"app.py": b"print('uncompressed tar')\n"},
        mode="w",
    )
    res_tar = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions/upload",
        files={"file": ("project.tar", tar_bytes, "application/x-tar")},
        data={"revision_identifier": "rev-tar"},
    )
    assert res_tar.status_code == 201
    assert res_tar.json()["status"] == "completed"


def test_upload_unsupported_archive_format_rejected_with_422(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    """Test that uploading non-supported file formats returns 422."""
    project_id, repo_id, _ = _setup_project_and_repo(client, set_current_user)

    res = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions/upload",
        files={"file": ("malicious.exe", b"MZ...", "application/octet-stream")},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "unsupported_archive_format"

    res_rar = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions/upload",
        files={"file": ("archive.rar", b"Rar!...", "application/x-rar")},
    )
    assert res_rar.status_code == 422
    assert res_rar.json()["error"]["code"] == "unsupported_archive_format"


def test_trigger_ingestion_github_api_success(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test triggering ingestion from public GitHub repo via JSON endpoint."""
    project_id, repo_id, _ = _setup_project_and_repo(client, set_current_user)

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        tar_bytes = _create_tar_bytes(
            {
                "Hello-World-main/src/index.js": b"console.log('hi');\n",
                "Hello-World-main/README.md": b"# GitHub README\n",
            },
            mode="w:gz",
        )
        return httpx.Response(200, content=tar_bytes, request=request)

    real_init = httpx.Client.__init__

    def patched_init(self: httpx.Client, *args: object, **kwargs: object) -> None:
        kwargs["transport"] = httpx.MockTransport(mock_transport_handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)

    res = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions",
        json={
            "source_type": "github",
            "repository_url": "https://github.com/octocat/Hello-World",
            "ref": "main",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "completed"
    assert data["source_type"] == "github"
    assert "https://github.com/octocat/Hello-World@main" in data["source_reference"]


def test_trigger_ingestion_github_invalid_inputs_rejected_with_422(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    """Test that invalid GitHub URL, ref, and source type return 422."""
    project_id, repo_id, _ = _setup_project_and_repo(client, set_current_user)

    # 1. Invalid URL (non-https)
    res_url = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions",
        json={
            "source_type": "github",
            "repository_url": "http://github.com/octocat/Hello-World",
        },
    )
    assert res_url.status_code == 422
    assert res_url.json()["error"]["code"] == "invalid_github_url"

    # 2. Invalid Git ref (shell injection chars)
    res_ref = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions",
        json={
            "source_type": "github",
            "repository_url": "https://github.com/octocat/Hello-World",
            "ref": "main;rm -rf /",
        },
    )
    assert res_ref.status_code == 422
    assert res_ref.json()["error"]["code"] == "invalid_github_ref"

    # 3. Invalid source type
    res_type = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions",
        json={
            "source_type": "unknown_source_type",
            "source_reference": "data/test",
        },
    )
    assert res_type.status_code == 422
    assert res_type.json()["error"]["code"] == "invalid_source_type"


def test_trigger_ingestion_server_path_api_success_and_failures(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test server_path mode: allowed directory, jailbreak attempt, and missing path."""
    from backend.platform.config import get_settings

    project_id, repo_id, _ = _setup_project_and_repo(client, set_current_user)

    staged_root = tmp_path / "staged"
    staged_root.mkdir()
    monkeypatch.setattr(get_settings(), "allowed_source_roots", [str(staged_root)])

    # 1. Valid staged directory within allowed roots
    staged_dir = staged_root / "my_project"
    staged_dir.mkdir()
    (staged_dir / "index.js").write_text("console.log('staged');")

    res_ok = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions",
        json={
            "source_type": "server_path",
            "source_reference": str(staged_dir),
            "revision_identifier": "rev-staged-1",
        },
    )
    assert res_ok.status_code == 201
    assert res_ok.json()["status"] == "completed"
    assert res_ok.json()["source_type"] == "server_path"

    # 2. Path outside allowed roots -> 403 Forbidden
    res_forbidden = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions",
        json={
            "source_type": "server_path",
            "source_reference": "/etc/passwd",
        },
    )
    assert res_forbidden.status_code == 403
    assert res_forbidden.json()["error"]["code"] == "server_path_not_allowed"

    # 3. Path inside allowed roots but not found on disk -> 404 Not Found
    res_not_found = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions",
        json={
            "source_type": "server_path",
            "source_reference": str(staged_root / "missing_folder"),
        },
    )
    assert res_not_found.status_code == 404
    assert res_not_found.json()["error"]["code"] == "server_path_not_found"


def test_trigger_ingestion_github_error_status_mappings(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that GitHub 404 and 429 errors map to 404 and 429 HTTP status codes."""
    project_id, repo_id, _ = _setup_project_and_repo(client, set_current_user)

    # 1. GitHub 404 Not Found -> 404 github_repository_not_found
    def mock_404_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    real_init = httpx.Client.__init__

    def patched_init_404(self: httpx.Client, *args: object, **kwargs: object) -> None:
        kwargs["transport"] = httpx.MockTransport(mock_404_transport)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init_404)

    res_404 = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions",
        json={
            "source_type": "github",
            "repository_url": "https://github.com/octocat/NonExistentRepo",
        },
    )
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "github_repository_not_found"

    # 2. GitHub 429 Rate Limit -> 429 github_rate_limit_exceeded
    def mock_429_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    def patched_init_429(self: httpx.Client, *args: object, **kwargs: object) -> None:
        kwargs["transport"] = httpx.MockTransport(mock_429_transport)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init_429)

    res_429 = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}/ingestions",
        json={
            "source_type": "github",
            "repository_url": "https://github.com/octocat/Hello-World",
        },
    )
    assert res_429.status_code == 429
    assert res_429.json()["error"]["code"] == "github_rate_limit_exceeded"
