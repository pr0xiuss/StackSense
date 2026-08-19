"""StackSense logging configuration."""

import logging
import logging.config

from backend.platform.config import get_settings


def configure_logging() -> None:
    """Configure application-wide logging."""
    settings = get_settings()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s | %(levelname)s | "
                        "%(name)s | %(message)s"
                    ),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": settings.log_level,
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": settings.log_level,
                "handlers": ["console"],
            },
        }
    )