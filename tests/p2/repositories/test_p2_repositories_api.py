"""End-to-end API integration tests for Repositories."""

from collections.abc import Callable
from uuid import UUID, uuid4

from fastapi.testclient import TestClient


def _create_project_via_api(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
    name: str = "Repo API Project",
) -> tuple[str, UUID]:
    owner_id = uuid4()
    set_current_user(owner_id)

    response = client.post(
        "/api/v1/projects",
        json={"name": name, "description": "Project for repository testing"},
    )
    assert response.status_code == 201
    return response.json()["id"], owner_id


def _grant_role(
    client: TestClient,
    project_id: str,
    target_user_id: UUID,
    role: str,
    owner_id: UUID,
    set_current_user: Callable[[UUID], None],
) -> None:
    set_current_user(owner_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={"user_id": str(target_user_id), "role": role},
    )
    assert response.status_code == 201


def test_create_repository_success(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)

    response = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={
            "name": "core-backend",
            "description": "FastAPI backend service",
        },
    )
    assert response.status_code == 201
    data = response.json()

    assert UUID(data["id"])
    assert data["project_id"] == project_id
    assert data["name"] == "core-backend"
    assert data["description"] == "FastAPI backend service"
    assert data["status"] == "registered"
    assert "created_at" in data
    assert "updated_at" in data


def test_create_repository_validation_error(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, _ = _create_project_via_api(client, set_current_user)

    # Empty name
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": ""},
    )
    assert response.status_code == 422

    # Missing name
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"description": "Missing name field"},
    )
    assert response.status_code == 422


def test_create_repository_duplicate_name_conflict(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, _ = _create_project_via_api(client, set_current_user)

    client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "duplicate-repo"},
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "duplicate-repo"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "repository_already_exists"


def test_create_repository_by_developer_allowed(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)
    dev_id = uuid4()
    _grant_role(client, project_id, dev_id, "developer", owner_id, set_current_user)

    set_current_user(dev_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "dev-created-repo"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "dev-created-repo"


def test_create_repository_by_viewer_forbidden(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)
    viewer_id = uuid4()
    _grant_role(client, project_id, viewer_id, "viewer", owner_id, set_current_user)

    set_current_user(viewer_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "viewer-forbidden"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "project_access_denied"


def test_create_repository_unauthorized_user_forbidden(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, _ = _create_project_via_api(client, set_current_user)
    set_current_user(uuid4())

    response = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "unauthorized-repo"},
    )
    assert response.status_code == 403


def test_get_repository_success(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, _ = _create_project_via_api(client, set_current_user)

    create_resp = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "get-target-repo"},
    )
    repo_id = create_resp.json()["id"]

    response = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
    )
    assert response.status_code == 200
    assert response.json()["id"] == repo_id
    assert response.json()["name"] == "get-target-repo"


def test_get_repository_by_viewer_allowed(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)
    viewer_id = uuid4()
    _grant_role(client, project_id, viewer_id, "viewer", owner_id, set_current_user)

    set_current_user(owner_id)
    create_resp = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "viewer-readable"},
    )
    repo_id = create_resp.json()["id"]

    set_current_user(viewer_id)
    response = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
    )
    assert response.status_code == 200
    assert response.json()["id"] == repo_id


def test_get_repository_nonexistent_returns_404(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, _ = _create_project_via_api(client, set_current_user)
    missing_id = uuid4()

    response = client.get(
        f"/api/v1/projects/{project_id}/repositories/{missing_id}",
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "repository_not_found"


def test_get_repository_mismatched_project_returns_404(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_a, owner_a = _create_project_via_api(client, set_current_user, "Proj A")
    project_b, owner_b = _create_project_via_api(client, set_current_user, "Proj B")

    set_current_user(owner_a)
    create_resp = client.post(
        f"/api/v1/projects/{project_a}/repositories",
        json={"name": "proj-a-repo"},
    )
    repo_a_id = create_resp.json()["id"]

    # Target repo_a through project_b as user_b (authorized for project_b)
    set_current_user(owner_b)
    response = client.get(
        f"/api/v1/projects/{project_b}/repositories/{repo_a_id}",
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "repository_not_found"


def test_list_repositories_with_pagination(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, _ = _create_project_via_api(client, set_current_user)

    for i in range(4):
        client.post(
            f"/api/v1/projects/{project_id}/repositories",
            json={"name": f"pagination-repo-{i}"},
        )

    response = client.get(
        f"/api/v1/projects/{project_id}/repositories?limit=2&offset=1",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "pagination-repo-1"
    assert data[1]["name"] == "pagination-repo-2"


def test_list_repositories_by_viewer_allowed(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)
    viewer_id = uuid4()
    _grant_role(client, project_id, viewer_id, "viewer", owner_id, set_current_user)

    set_current_user(owner_id)
    client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "repo-for-listing"},
    )

    set_current_user(viewer_id)
    response = client.get(
        f"/api/v1/projects/{project_id}/repositories",
    )
    assert response.status_code == 200
    assert any(r["name"] == "repo-for-listing" for r in response.json())


def test_update_repository_success(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, _ = _create_project_via_api(client, set_current_user)

    create_resp = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "before-update", "description": "old"},
    )
    repo_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
        json={"name": "after-update", "description": "new"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "after-update"
    assert response.json()["description"] == "new"


def test_update_repository_by_developer_allowed(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)
    dev_id = uuid4()
    _grant_role(client, project_id, dev_id, "developer", owner_id, set_current_user)

    set_current_user(owner_id)
    create_resp = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "dev-update-target"},
    )
    repo_id = create_resp.json()["id"]

    set_current_user(dev_id)
    response = client.patch(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
        json={"description": "Updated by Developer"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated by Developer"


def test_update_repository_by_viewer_forbidden(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)
    viewer_id = uuid4()
    _grant_role(client, project_id, viewer_id, "viewer", owner_id, set_current_user)

    set_current_user(owner_id)
    create_resp = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "viewer-patch-target"},
    )
    repo_id = create_resp.json()["id"]

    set_current_user(viewer_id)
    response = client.patch(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
        json={"name": "viewer-hacked"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "project_access_denied"


def test_update_repository_duplicate_name_conflict(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, _ = _create_project_via_api(client, set_current_user)

    client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "existing-repo"},
    )
    create_resp2 = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "target-to-rename"},
    )
    repo2_id = create_resp2.json()["id"]

    response = client.patch(
        f"/api/v1/projects/{project_id}/repositories/{repo2_id}",
        json={"name": "existing-repo"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "repository_already_exists"


def test_delete_repository_by_owner_success(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, _ = _create_project_via_api(client, set_current_user)

    create_resp = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "delete-me"},
    )
    repo_id = create_resp.json()["id"]

    delete_resp = client.delete(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
    )
    assert delete_resp.status_code == 204

    # Verify subsequent GET returns 404
    get_resp = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
    )
    assert get_resp.status_code == 404


def test_delete_repository_by_admin_success(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)
    admin_id = uuid4()
    _grant_role(client, project_id, admin_id, "admin", owner_id, set_current_user)

    set_current_user(owner_id)
    create_resp = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "admin-delete-target"},
    )
    repo_id = create_resp.json()["id"]

    set_current_user(admin_id)
    delete_resp = client.delete(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
    )
    assert delete_resp.status_code == 204


def test_delete_repository_by_developer_forbidden(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)
    dev_id = uuid4()
    _grant_role(client, project_id, dev_id, "developer", owner_id, set_current_user)

    set_current_user(owner_id)
    create_resp = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "dev-delete-forbidden"},
    )
    repo_id = create_resp.json()["id"]

    set_current_user(dev_id)
    delete_resp = client.delete(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
    )
    assert delete_resp.status_code == 403
    assert delete_resp.json()["error"]["code"] == "project_access_denied"

    # Confirm repository was NOT deleted
    set_current_user(owner_id)
    get_resp = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
    )
    assert get_resp.status_code == 200


def test_delete_repository_by_viewer_forbidden(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    project_id, owner_id = _create_project_via_api(client, set_current_user)
    viewer_id = uuid4()
    _grant_role(client, project_id, viewer_id, "viewer", owner_id, set_current_user)

    set_current_user(owner_id)
    create_resp = client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "viewer-delete-forbidden"},
    )
    repo_id = create_resp.json()["id"]

    set_current_user(viewer_id)
    delete_resp = client.delete(
        f"/api/v1/projects/{project_id}/repositories/{repo_id}",
    )
    assert delete_resp.status_code == 403
    assert delete_resp.json()["error"]["code"] == "project_access_denied"
