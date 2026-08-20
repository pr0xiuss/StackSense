"""StackSense API exception handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.platform.errors import StackSenseError


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

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
