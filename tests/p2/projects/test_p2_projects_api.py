from collections.abc import Callable
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from backend.platform.projects.domain.project_access import ProjectAccess
from backend.platform.projects.domain.project_role import ProjectRole


def test_create_project(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "StackSense",
            "description": "Code intelligence platform",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert UUID(data["id"])
    assert data["name"] == "StackSense"
    assert data["description"] == "Code intelligence platform"
    assert "created_at" in data
    assert "updated_at" in data


def test_list_projects(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Project One",
            "description": "First project",
        },
    )

    assert create_response.status_code == 201

    response = client.get("/api/v1/projects")

    assert response.status_code == 200

    data = response.json()

    assert len(data) >= 1
    assert any(project["name"] == "Project One" for project in data)


def test_get_project(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Project Two",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == project_id
    assert data["name"] == "Project Two"


def test_get_nonexistent_project(client: TestClient) -> None:
    project_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert response.status_code == 404


def test_delete_project(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Project To Delete",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/projects/{project_id}",
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert get_response.status_code == 404


def test_project_access_is_required(
    client: TestClient,
) -> None:
    project_id = "11111111-1111-1111-1111-111111111111"

    response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert response.status_code == 404


def test_project_access_is_user_scoped(
    client: TestClient,
    set_current_user: callable,
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    other_user_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Private Project",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    set_current_user(other_user_id)

    response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert response.status_code == 403


def test_viewer_cannot_delete_project(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    viewer_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Viewer Delete Test",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    grant_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(viewer_id),
            "role": "viewer",
        },
    )

    assert grant_response.status_code == 201

    set_current_user(viewer_id)

    delete_response = client.delete(
        f"/api/v1/projects/{project_id}",
    )

    assert delete_response.status_code == 403

    get_response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert get_response.status_code == 200


def test_grant_project_access(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Access Grant Project",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]
    user_id = "00000000-0000-0000-0000-000000000002"

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": user_id,
            "role": "viewer",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["project_id"] == project_id
    assert data["user_id"] == user_id
    assert data["role"] == "viewer"


def test_update_project_access_role(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Access Role Project",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]
    user_id = "00000000-0000-0000-0000-000000000002"

    grant_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": user_id,
            "role": "viewer",
        },
    )

    assert grant_response.status_code == 201

    response = client.patch(
        f"/api/v1/projects/{project_id}/access/{user_id}",
        json={
            "role": "developer",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["project_id"] == project_id
    assert data["user_id"] == user_id
    assert data["role"] == "developer"


def test_revoke_project_access(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Access Revoke Project",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]
    user_id = "00000000-0000-0000-0000-000000000002"

    grant_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": user_id,
            "role": "viewer",
        },
    )

    assert grant_response.status_code == 201

    response = client.delete(
        f"/api/v1/projects/{project_id}/access/{user_id}",
    )

    assert response.status_code == 204


def test_grant_duplicate_project_access_returns_conflict(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Duplicate Access Project",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]
    user_id = "00000000-0000-0000-0000-000000000002"

    first_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": user_id,
            "role": "viewer",
        },
    )

    assert first_response.status_code == 201

    second_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": user_id,
            "role": "developer",
        },
    )

    assert second_response.status_code == 409

    data = second_response.json()

    assert data["error"]["code"] == "project_access_already_exists"


def test_update_nonexistent_project_access_returns_not_found(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Missing Access Project",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]
    user_id = "00000000-0000-0000-0000-000000000002"

    response = client.patch(
        f"/api/v1/projects/{project_id}/access/{user_id}",
        json={
            "role": "developer",
        },
    )

    assert response.status_code == 404

    data = response.json()

    assert data["error"]["code"] == "project_access_not_found"


def test_revoke_nonexistent_project_access_returns_not_found(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Missing Revoke Project",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]
    user_id = "00000000-0000-0000-0000-000000000002"

    response = client.delete(
        f"/api/v1/projects/{project_id}/access/{user_id}",
    )

    assert response.status_code == 404

    data = response.json()

    assert data["error"]["code"] == "project_access_not_found"


def test_admin_can_delete_project(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    admin_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Admin Delete Test",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    grant_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(admin_id),
            "role": "admin",
        },
    )

    assert grant_response.status_code == 201

    set_current_user(admin_id)

    delete_response = client.delete(
        f"/api/v1/projects/{project_id}",
    )

    assert delete_response.status_code == 204


def test_developer_cannot_delete_project(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    developer_id = UUID(
        "00000000-0000-0000-0000-000000000003",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Developer Delete Test",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    grant_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(developer_id),
            "role": "developer",
        },
    )

    assert grant_response.status_code == 201

    set_current_user(developer_id)

    delete_response = client.delete(
        f"/api/v1/projects/{project_id}",
    )

    assert delete_response.status_code == 403

    get_response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert get_response.status_code == 200


def test_project_role_permission_matrix() -> None:
    owner = ProjectAccess(
        project_id=uuid4(),
        user_id=uuid4(),
        role=ProjectRole.OWNER,
    )

    admin = ProjectAccess(
        project_id=uuid4(),
        user_id=uuid4(),
        role=ProjectRole.ADMIN,
    )

    developer = ProjectAccess(
        project_id=uuid4(),
        user_id=uuid4(),
        role=ProjectRole.DEVELOPER,
    )

    viewer = ProjectAccess(
        project_id=uuid4(),
        user_id=uuid4(),
        role=ProjectRole.VIEWER,
    )

    assert owner.can_read()
    assert owner.can_create()
    assert owner.can_update()
    assert owner.can_delete()

    assert admin.can_read()
    assert admin.can_create()
    assert admin.can_update()
    assert admin.can_delete()

    assert developer.can_read()
    assert developer.can_create()
    assert developer.can_update()
    assert not developer.can_delete()

    assert viewer.can_read()
    assert not viewer.can_create()
    assert not viewer.can_update()
    assert not viewer.can_delete()


def test_admin_can_manage_project_access(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    admin_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )
    member_id = UUID(
        "00000000-0000-0000-0000-000000000003",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Admin Access Management",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    grant_admin_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(admin_id),
            "role": "admin",
        },
    )

    assert grant_admin_response.status_code == 201

    set_current_user(admin_id)

    grant_member_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(member_id),
            "role": "viewer",
        },
    )

    assert grant_member_response.status_code == 201

    assert grant_member_response.json()["role"] == "viewer"


def test_developer_cannot_manage_project_access(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    developer_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )
    member_id = UUID(
        "00000000-0000-0000-0000-000000000003",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Developer Access Management",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    grant_developer_response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(developer_id),
            "role": "developer",
        },
    )

    assert grant_developer_response.status_code == 201

    set_current_user(developer_id)

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(member_id),
            "role": "viewer",
        },
    )

    assert response.status_code == 403


def test_project_access_isolation(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    user_a = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    user_b = UUID(
        "00000000-0000-0000-0000-000000000002",
    )

    set_current_user(user_a)

    project_a_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Project A",
        },
    )

    assert project_a_response.status_code == 201

    project_a_id = project_a_response.json()["id"]

    set_current_user(user_b)

    project_b_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Project B",
        },
    )

    assert project_b_response.status_code == 201

    project_b_id = project_b_response.json()["id"]

    set_current_user(user_a)

    response = client.get(
        f"/api/v1/projects/{project_b_id}",
    )

    assert response.status_code == 403

    response = client.get(
        f"/api/v1/projects/{project_a_id}",
    )

    assert response.status_code == 200


def test_admin_can_change_project_member_role(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    admin_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )
    member_id = UUID(
        "00000000-0000-0000-0000-000000000003",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={"name": "Admin Role Change"},
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(admin_id),
            "role": "admin",
        },
    )

    assert response.status_code == 201

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(member_id),
            "role": "viewer",
        },
    )

    assert response.status_code == 201

    set_current_user(admin_id)

    response = client.patch(
        f"/api/v1/projects/{project_id}/access/{member_id}",
        json={"role": "developer"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "developer"


def test_developer_cannot_change_project_member_role(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    developer_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )
    member_id = UUID(
        "00000000-0000-0000-0000-000000000003",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={"name": "Developer Role Change"},
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(developer_id),
            "role": "developer",
        },
    )

    assert response.status_code == 201

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(member_id),
            "role": "viewer",
        },
    )

    assert response.status_code == 201

    set_current_user(developer_id)

    response = client.patch(
        f"/api/v1/projects/{project_id}/access/{member_id}",
        json={"role": "developer"},
    )

    assert response.status_code == 403


def test_viewer_cannot_change_project_member_role(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    viewer_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )
    member_id = UUID(
        "00000000-0000-0000-0000-000000000003",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={"name": "Viewer Role Change"},
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(viewer_id),
            "role": "viewer",
        },
    )

    assert response.status_code == 201

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(member_id),
            "role": "viewer",
        },
    )

    assert response.status_code == 201

    set_current_user(viewer_id)

    response = client.patch(
        f"/api/v1/projects/{project_id}/access/{member_id}",
        json={"role": "developer"},
    )

    assert response.status_code == 403


def test_non_member_cannot_change_project_member_role(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    member_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )
    outsider_id = UUID(
        "00000000-0000-0000-0000-000000000003",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={"name": "Unauthorized Role Change"},
    )

    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(member_id),
            "role": "viewer",
        },
    )

    assert response.status_code == 201

    set_current_user(outsider_id)

    response = client.patch(
        f"/api/v1/projects/{project_id}/access/{member_id}",
        json={"role": "developer"},
    )

    assert response.status_code == 403


def test_non_member_cannot_revoke_project_access(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    member_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )
    outsider_id = UUID(
        "00000000-0000-0000-0000-000000000003",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={"name": "Unauthorized Revoke"},
    )

    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(member_id),
            "role": "viewer",
        },
    )

    assert response.status_code == 201

    set_current_user(outsider_id)

    response = client.delete(
        f"/api/v1/projects/{project_id}/access/{member_id}",
    )

    assert response.status_code == 403

    set_current_user(member_id)

    response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert response.status_code == 200


def test_revoked_member_loses_project_access(
    client: TestClient,
    set_current_user: Callable[[UUID], None],
) -> None:
    owner_id = UUID(
        "00000000-0000-0000-0000-000000000001",
    )
    member_id = UUID(
        "00000000-0000-0000-0000-000000000002",
    )

    set_current_user(owner_id)

    create_response = client.post(
        "/api/v1/projects",
        json={"name": "Revocation Access"},
    )

    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/access",
        json={
            "user_id": str(member_id),
            "role": "developer",
        },
    )

    assert response.status_code == 201

    set_current_user(member_id)

    response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert response.status_code == 200

    set_current_user(owner_id)

    response = client.delete(
        f"/api/v1/projects/{project_id}/access/{member_id}",
    )

    assert response.status_code == 204

    set_current_user(member_id)

    response = client.get(
        f"/api/v1/projects/{project_id}",
    )

    assert response.status_code == 403
