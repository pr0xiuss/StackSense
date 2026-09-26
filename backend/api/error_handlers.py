"""StackSense API exception handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.platform.errors import ErrorCategory, StackSenseError


def register_exception_handlers(application: FastAPI) -> None:
    """Register StackSense application exception handlers."""
    logger = logging.getLogger(__name__)

    @application.exception_handler(StackSenseError)
    async def handle_stacksense_error(
        request: Request,
        exc: StackSenseError,
    ) -> JSONResponse:
        """Translate an application error into the public API contract."""
        logger.error(
            "application_error",
            extra={
                "error_code": exc.code,
                "error_category": exc.category.value,
                "error_scope": exc.scope.value,
            },
        )

        status_codes = {
            "project_access_already_exists": 409,
            "project_access_not_found": 404,
            "repository_not_found": 404,
            "repository_already_exists": 409,
            "invalid_credentials": 401,
            "authentication_required": 401,
            "invalid_token": 401,
            "token_expired": 401,
            "user_inactive": 401,
            "password_policy_violation": 422,
            "user_already_exists": 409,
        }

        status_code = status_codes.get(
            exc.code,
            (
                401
                if exc.category is ErrorCategory.AUTHENTICATION
                else 403 if exc.category is ErrorCategory.AUTHORIZATION else 500
            ),
        )

        headers: dict[str, str] = {}
        if exc.category is ErrorCategory.AUTHENTICATION:
            headers["WWW-Authenticate"] = "Bearer"

        return JSONResponse(
            status_code=status_code,
            headers=headers if headers else None,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
