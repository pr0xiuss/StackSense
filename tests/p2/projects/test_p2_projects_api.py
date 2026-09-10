from uuid import UUID

from fastapi.testclient import TestClient


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
