"""Regression tests for token authentication across protected API endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_protected_routes_reject_unauthenticated_requests(
    unauthenticated_client: TestClient,
) -> None:
    # 1. Projects listing
    r_projects = unauthenticated_client.get("/api/v1/projects")
    assert r_projects.status_code == 401
    assert r_projects.headers.get("WWW-Authenticate") == "Bearer"
    assert r_projects.json()["error"]["code"] == "authentication_required"

    # 2. Project creation
    r_create_project = unauthenticated_client.post(
        "/api/v1/projects",
        json={"name": "Secret Project"},
    )
    assert r_create_project.status_code == 401
    assert r_create_project.headers.get("WWW-Authenticate") == "Bearer"

    # 3. Repositories listing
    r_repos = unauthenticated_client.get(f"/api/v1/projects/{uuid4()}/repositories")
    assert r_repos.status_code == 401
    assert r_repos.headers.get("WWW-Authenticate") == "Bearer"


def test_authenticated_user_can_create_and_manage_project(
    unauthenticated_client: TestClient,
) -> None:
    # 1. Register & login
    tag = uuid4().hex[:8]
    email = f"owner-{tag}@stacksense.local"
    password = "ProjectPassword123"

    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    login_res = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. List projects initially — empty
    list_res = unauthenticated_client.get("/api/v1/projects", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json() == []

    # 3. Create project
    create_res = unauthenticated_client.post(
        "/api/v1/projects",
        json={"name": f"P-{tag}", "description": "Created with real JWT"},
        headers=headers,
    )
    assert create_res.status_code == 201
    project_data = create_res.json()
    project_id = project_data["id"]

    # 4. List projects — contains newly created project
    list_again = unauthenticated_client.get("/api/v1/projects", headers=headers)
    assert list_again.status_code == 200
    assert len(list_again.json()) == 1
    assert list_again.json()[0]["id"] == project_id

    # 5. Create repository under project
    repo_res = unauthenticated_client.post(
        f"/api/v1/projects/{project_id}/repositories",
        json={"name": "core-repo", "description": "Core repository"},
        headers=headers,
    )
    assert repo_res.status_code == 201
    assert repo_res.json()["name"] == "core-repo"


def test_cross_project_isolation_with_real_bearer_tokens(
    unauthenticated_client: TestClient,
) -> None:
    # User A
    tag_a = uuid4().hex[:8]
    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": f"usera-{tag_a}@stacksense.local", "password": "PasswordA123"},
    )
    token_a = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": f"usera-{tag_a}@stacksense.local", "password": "PasswordA123"},
    ).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User B
    tag_b = uuid4().hex[:8]
    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": f"userb-{tag_b}@stacksense.local", "password": "PasswordB123"},
    )
    token_b = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": f"userb-{tag_b}@stacksense.local", "password": "PasswordB123"},
    ).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates Project A
    proj_a = unauthenticated_client.post(
        "/api/v1/projects",
        json={"name": f"ProjectA-{tag_a}"},
        headers=headers_a,
    ).json()
    project_a_id = proj_a["id"]

    # User B cannot access Project A (404 Not Found to prevent enumeration)
    get_res = unauthenticated_client.get(
        f"/api/v1/projects/{project_a_id}",
        headers=headers_b,
    )
    assert get_res.status_code == 404

    # User B cannot list repositories of Project A
    repos_res = unauthenticated_client.get(
        f"/api/v1/projects/{project_a_id}/repositories",
        headers=headers_b,
    )
    assert repos_res.status_code == 403
