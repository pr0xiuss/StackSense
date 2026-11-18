"""Application composition only; M1 does not import its downstream producers."""

from backend.platform.delivery.registry import WorkHandlerRegistry
from backend.platform.delivery.service import DeliveryCoordinator
from backend.platform.knowledge.dependencies import configured_search_registrations


def get_output_handler_registry() -> WorkHandlerRegistry:
    return WorkHandlerRegistry(configured_search_registrations())


def get_output_delivery_coordinator() -> DeliveryCoordinator | None:
    from backend.platform.config import get_settings
    from backend.platform.delivery.dependencies import build_delivery_coordinator
    from backend.platform.dependency_injection import get_database_engine
    from backend.worker.celery_app import celery_app

    return build_delivery_coordinator(
        get_database_engine(),
        get_settings(),
        celery_app,
        registry=get_output_handler_registry(),
    )
