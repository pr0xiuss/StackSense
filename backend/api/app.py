"""StackSense FastAPI application bootstrap."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.platform.config import get_settings
from backend.platform.errors import StackSenseError
from backend.platform.health import router as health_router
from backend.platform.logging import configure_logging


def create_application() -> FastAPI:
    """Create and configure the StackSense FastAPI application."""
    settings = get_settings()

    configure_logging()

    logger = logging.getLogger(__name__)
    logger.info(
        "application_started",
        extra={
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "environment": settings.app_env,
        },
    )

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )

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

    application.include_router(health_router)

    return application


app = create_application()
