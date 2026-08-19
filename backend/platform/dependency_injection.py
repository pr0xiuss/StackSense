"""StackSense dependency injection foundation."""

from functools import lru_cache

from backend.infra.postgres import Database
from backend.platform.config import Settings, get_settings
from backend.platform.database import DatabaseSettings


@lru_cache
def get_application_settings() -> Settings:
    """Provide application settings through the dependency boundary."""
    return get_settings()


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Provide database settings through the dependency boundary."""
    return DatabaseSettings()


@lru_cache
def get_database() -> Database:
    """Provide the PostgreSQL database infrastructure."""
    return Database(get_database_settings())