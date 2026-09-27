"""API integration tests for /api/v1/auth endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.platform.dependency_injection import get_database
from backend.platform.identity.infra.user_repo import SqlAlchemyUserRepository


def test_register_success(unauthenticated_client: TestClient) -> None:
    tag = uuid4().hex[:8]
    email = f"register-{tag}@stacksense.local"
    password = "StrongPassword123"

    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["email"] == email
    assert data["is_active"] is True
    assert data["created_at"] is not None
    assert "password" not in data
    assert "password_hash" not in data

    # Verify user and hashed credential exist in database
    database = get_database()
    gen = database.session()
    sess = next(gen)
    try:
        repo = SqlAlchemyUserRepository(sess)
        cred = repo.get_credential_by_user_id(uuid4() if False else data["id"])
        assert cred is not None
        assert cred.password_hash.startswith("$2b$")
        assert cred.password_hash != password
    finally:
        gen.close()


def test_register_normalizes_email(unauthenticated_client: TestClient) -> None:
    tag = uuid4().hex[:8]
    email_raw = f"  CASEREG-{tag.upper()}@STACKSENSE.LOCAL  "
    expected_email = f"casereg-{tag.lower()}@stacksense.local"

    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email_raw, "password": "ValidPassword123"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == expected_email


def test_register_duplicate_email_returns_409(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email = f"dup-{tag}@stacksense.local"

    # First registration
    r1 = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "ValidPassword123"},
    )
    assert r1.status_code == 201

    # Second registration with same email
    r2 = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "AnotherPassword123"},
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "user_already_exists"

    # Third registration with case variation
    r3 = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email.upper(), "password": "AnotherPassword123"},
    )
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "user_already_exists"


def test_register_invalid_password_policy_returns_422(
    unauthenticated_client: TestClient,
) -> None:
    # Too short (< 8 chars)
    short_email = f"short-{uuid4().hex[:8]}@stacksense.local"
    r_short = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": short_email, "password": "short"},
    )
    assert r_short.status_code == 422

    # Too long (> 128 chars)
    long_email = f"long-{uuid4().hex[:8]}@stacksense.local"
    r_long = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": long_email, "password": "a" * 129},
    )
    assert r_long.status_code == 422


def test_register_empty_email_returns_422(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": "   ", "password": "ValidPassword123"},
    )
    assert response.status_code == 422


def test_login_success(unauthenticated_client: TestClient) -> None:
    tag = uuid4().hex[:8]
    email = f"login-{tag}@stacksense.local"
    password = "CorrectPassword123"

    # Register first
    reg = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg.status_code == 201

    # Login
    login_res = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["access_token"] is not None
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600


def test_login_wrong_password_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email = f"wrongpw-{tag}@stacksense.local"

    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "RightPassword123"},
    )

    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword999"},
    )
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_nonexistent_user_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    ghost_email = f"ghost-{uuid4().hex[:8]}@stacksense.local"
    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": ghost_email, "password": "AnyPassword123"},
    )
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_get_me_success_with_bearer_token(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email = f"getme-{tag}@stacksense.local"
    password = "MyPassword123"

    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )

    login_res = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["access_token"]

    me_res = unauthenticated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    user_data = me_res.json()
    assert user_data["email"] == email
    assert user_data["is_active"] is True
    assert "password" not in user_data
    assert "password_hash" not in user_data


def test_get_me_unauthenticated_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["error"]["code"] == "authentication_required"


def test_get_me_with_invalid_token_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.fake.token"},
    )
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["error"]["code"] == "invalid_token"
