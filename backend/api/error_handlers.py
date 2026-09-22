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
        }

        status_code = status_codes.get(
            exc.code,
            403 if exc.category is ErrorCategory.AUTHORIZATION else 500,
        )

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
