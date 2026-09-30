"""Tests for Authentication error contract and API exception handler translation."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.platform.errors import (
    AuthenticationRequiredError,
    InvalidCredentialsError,
    InvalidTokenError,
    PasswordPolicyError,
    TokenExpiredError,
    UserInactiveError,
)


def create_error_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/error/invalid-credentials")
    async def trigger_invalid_credentials() -> None:
        raise InvalidCredentialsError()

    @app.get("/error/auth-required")
    async def trigger_auth_required() -> None:
        raise AuthenticationRequiredError()

    @app.get("/error/invalid-token")
    async def trigger_invalid_token() -> None:
        raise InvalidTokenError()

    @app.get("/error/token-expired")
    async def trigger_token_expired() -> None:
        raise TokenExpiredError()

    @app.get("/error/user-inactive")
    async def trigger_user_inactive() -> None:
        raise UserInactiveError()

    @app.get("/error/password-policy")
    async def trigger_password_policy() -> None:
        raise PasswordPolicyError("Password must be at least 8 characters.")

    return app


@pytest.fixture
def error_client() -> TestClient:
    return TestClient(create_error_test_app())


def test_invalid_credentials_error_returns_401_with_header(
    error_client: TestClient,
) -> None:
    response = error_client.get("/error/invalid-credentials")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    data = response.json()
    assert data["error"]["code"] == "invalid_credentials"
    assert data["error"]["message"] == "Invalid email or password."


def test_auth_required_error_returns_401(error_client: TestClient) -> None:
    response = error_client.get("/error/auth-required")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    data = response.json()
    assert data["error"]["code"] == "authentication_required"


def test_invalid_token_error_returns_401(error_client: TestClient) -> None:
    response = error_client.get("/error/invalid-token")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    data = response.json()
    assert data["error"]["code"] == "invalid_token"


def test_token_expired_error_returns_401(error_client: TestClient) -> None:
    response = error_client.get("/error/token-expired")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    data = response.json()
    assert data["error"]["code"] == "token_expired"


def test_user_inactive_error_returns_401(error_client: TestClient) -> None:
    response = error_client.get("/error/user-inactive")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    data = response.json()
    assert data["error"]["code"] == "user_inactive"


def test_password_policy_error_returns_422(error_client: TestClient) -> None:
    response = error_client.get("/error/password-policy")
    assert response.status_code == 422
    assert "WWW-Authenticate" not in response.headers
    data = response.json()
    assert data["error"]["code"] == "password_policy_violation"
