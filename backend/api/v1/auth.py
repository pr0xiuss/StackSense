"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, status

from backend.platform.identity.application.auth_service import AuthenticationService
from backend.platform.identity.application.dependencies import (
    get_auth_service,
    get_current_user,
)
from backend.platform.identity.application.dto import (
    AuthTokenResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from backend.platform.identity.domain.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    request: RegisterRequest,
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> UserResponse:
    """Public self-registration endpoint."""
    user = auth_service.register(
        email=request.email,
        password=request.password,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and obtain access token",
)
def login(
    request: LoginRequest,
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> AuthTokenResponse:
    """Authenticate with email and password to receive a bearer token."""
    return auth_service.authenticate(
        email=request.email,
        password=request.password,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Retrieve profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
