"""End-to-end API integration tests for Ingestion endpoints."""

import io
import zipfile
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

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
