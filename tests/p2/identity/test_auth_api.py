"""API integration tests for /api/v1/auth endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.platform.dependency_injection import get_database
from backend.platform.identity.infra.user_repo import SqlAlchemyUserRepository


def test_register_success(unauthenticated_client: TestClient) -> None:
    tag = uuid4().hex[:8]
    email = f"register-{tag}@stacksense.local"
    username = f"reg_{tag}"
    password = "StrongPassword123"

    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["email"] == email
    assert data["username"] == username
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


def test_register_normalizes_email_and_username(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email_raw = f"  CASEREG-{tag.upper()}@STACKSENSE.LOCAL  "
    expected_email = f"casereg-{tag.lower()}@stacksense.local"
    username_raw = f"  USER_{tag.upper()}  "
    expected_username = f"user_{tag.lower()}"

    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": email_raw,
            "username": username_raw,
            "password": "ValidPassword123",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == expected_email
    assert response.json()["username"] == expected_username


def test_register_duplicate_email_returns_409(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email = f"dup-{tag}@stacksense.local"

    # First registration
    r1 = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": f"user1_{tag}",
            "password": "ValidPassword123",
        },
    )
    assert r1.status_code == 201

    # Second registration with same email
    r2 = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": f"user2_{tag}",
            "password": "AnotherPassword123",
        },
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "user_already_exists"

    # Third registration with case variation
    r3 = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": email.upper(),
            "username": f"user3_{tag}",
            "password": "AnotherPassword123",
        },
    )
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "user_already_exists"


def test_register_duplicate_username_returns_409(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    username = f"dupuser_{tag}"

    r1 = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"u1-{tag}@stacksense.local",
            "username": username,
            "password": "ValidPassword123",
        },
    )
    assert r1.status_code == 201

    r2 = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"u2-{tag}@stacksense.local",
            "username": username.upper(),
            "password": "AnotherPassword123",
        },
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "username_already_exists"


def test_register_invalid_username_returns_422(
    unauthenticated_client: TestClient,
) -> None:
    # Too short (< 3 chars)
    r_short = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"short-{uuid4().hex[:8]}@stacksense.local",
            "username": "ab",
            "password": "ValidPassword123",
        },
    )
    assert r_short.status_code == 422

    # Invalid characters (hyphen not allowed)
    r_hyphen = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"hyphen-{uuid4().hex[:8]}@stacksense.local",
            "username": "invalid-user",
            "password": "ValidPassword123",
        },
    )
    assert r_hyphen.status_code == 422


def test_register_invalid_password_policy_returns_422(
    unauthenticated_client: TestClient,
) -> None:
    # Too short (< 8 chars)
    short_email = f"short-{uuid4().hex[:8]}@stacksense.local"
    r_short = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": short_email,
            "username": f"user_{uuid4().hex[:6]}",
            "password": "short",
        },
    )
    assert r_short.status_code == 422

    # Too long (> 128 chars)
    long_email = f"long-{uuid4().hex[:8]}@stacksense.local"
    r_long = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": long_email,
            "username": f"user_{uuid4().hex[:6]}",
            "password": "a" * 129,
        },
    )
    assert r_long.status_code == 422


def test_register_empty_email_returns_422(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={
            "email": "   ",
            "username": f"user_{uuid4().hex[:6]}",
            "password": "ValidPassword123",
        },
    )
    assert response.status_code == 422


def test_login_success_with_email_and_username(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email = f"login-{tag}@stacksense.local"
    username = f"user_{tag}"
    password = "CorrectPassword123"

    # Register first
    reg = unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert reg.status_code == 201

    # Login via email
    login_res1 = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login_res1.status_code == 200
    data1 = login_res1.json()
    assert data1["access_token"] is not None
    assert data1["refresh_token"] is not None
    assert data1["token_type"] == "bearer"
    assert data1["expires_in"] == 3600
    assert data1["refresh_expires_in"] == 30 * 86400

    # Login via username
    login_res2 = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )
    assert login_res2.status_code == 200
    data2 = login_res2.json()
    assert data2["access_token"] is not None
    assert data2["refresh_token"] is not None


def test_login_wrong_password_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email = f"wrongpw-{tag}@stacksense.local"
    username = f"wp_{tag}"

    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "RightPassword123"},
    )

    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "WrongPassword999"},
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
        json={"identifier": ghost_email, "password": "AnyPassword123"},
    )
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_refresh_token_rotation(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email = f"refresh-{tag}@stacksense.local"
    username = f"ref_{tag}"
    password = "CorrectPassword123"

    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )

    login_res = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )
    refresh_token_1 = login_res.json()["refresh_token"]

    # Refresh
    refresh_res = unauthenticated_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert refresh_res.status_code == 200
    ref_data = refresh_res.json()
    assert ref_data["access_token"] is not None
    refresh_token_2 = ref_data["refresh_token"]
    assert refresh_token_2 != refresh_token_1

    # Old refresh token is revoked
    reused_res = unauthenticated_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert reused_res.status_code == 401
    assert reused_res.json()["error"]["code"] == "refresh_token_revoked"

    # New refresh token works
    valid_res = unauthenticated_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_2},
    )
    assert valid_res.status_code == 200


def test_logout_revokes_refresh_token(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email = f"logout-{tag}@stacksense.local"
    username = f"logout_{tag}"
    password = "CorrectPassword123"

    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )

    login_res = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )
    refresh_token = login_res.json()["refresh_token"]

    # Logout
    logout_res = unauthenticated_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 204

    # Now refresh should fail as revoked
    refresh_res = unauthenticated_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 401
    assert refresh_res.json()["error"]["code"] == "refresh_token_revoked"


def test_get_me_success_with_bearer_token(
    unauthenticated_client: TestClient,
) -> None:
    tag = uuid4().hex[:8]
    email = f"getme-{tag}@stacksense.local"
    username = f"gm_{tag}"
    password = "MyPassword123"

    unauthenticated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )

    login_res = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    token = login_res.json()["access_token"]

    me_res = unauthenticated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    user_data = me_res.json()
    assert user_data["email"] == email
    assert user_data["username"] == username
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
