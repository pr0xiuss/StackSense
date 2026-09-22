"""StackSense FastAPI application bootstrap."""

import logging

from fastapi import FastAPI

from backend.api.error_handlers import register_exception_handlers
from backend.api.v1.router import router as v1_router
from backend.platform.config import get_settings
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

    register_exception_handlers(application)
    application.include_router(v1_router)

    return application


app = create_application()
