"""Additive P5 composition over public providers; no global ORM Sessions."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.platform.analysis.application.dependencies import (
    get_analysis_lifecycle_service,
    get_platform_repository_gateway,
)
from backend.platform.config import Settings
from backend.platform.delivery.api_contracts import ManualRetryPolicy
from backend.platform.delivery.contracts import AttemptRetirementReader, DeliveryPolicy
from backend.platform.delivery.ownership import SqlAlchemyAttemptRetirementReader
from backend.platform.delivery.queue import CeleryDeliveryPublisher
from backend.platform.delivery.registry import WorkHandlerRegistry
from backend.platform.delivery.service import (
    DeliveryCoordinator,
    FleetManifest,
    RuntimeBudgets,
)
from backend.platform.delivery.source import PublishedVersionReader
from backend.platform.graph.source import SqlAlchemyPublishedArchitectureSource


def get_delivery_handler_registry() -> WorkHandlerRegistry:
    """Shared API/worker composition seam for producer-owned public factories.

    Future modules add reviewed bindings here (composition only), not lifecycle
    logic, discovery, dynamic plugin imports, or a second registry in each entry
    point. Until then the production registry is honestly empty.
    """
    return WorkHandlerRegistry()


def build_delivery_coordinator(
    engine: Engine,
    settings: Settings,
    app: Any,
    *,
    registry: WorkHandlerRegistry | None = None,
) -> DeliveryCoordinator | None:
    """Absent handlers/configuration mean unavailable, never fabricated success."""
    if (
        not settings.delivery_runtime_json
        or not settings.delivery_policy_json
        or not settings.delivery_fleet_json
    ):
        return None
    budgets = RuntimeBudgets.model_validate_json(settings.delivery_runtime_json)
    policy = DeliveryPolicy.model_validate_json(settings.delivery_policy_json)
    fleet = FleetManifest.model_validate_json(settings.delivery_fleet_json)
    if fleet.queue != settings.analysis_queue_name:
        raise ValueError("delivery must use the existing approved shared queue")

    @contextmanager
    def reader() -> Iterator[PublishedVersionReader]:
        with contextmanager(get_platform_repository_gateway)(settings) as gateway:
            with Session(engine, autoflush=False) as session:
                session.execute(
                    select(
                        func.set_config(
                            "statement_timeout",
                            str(max(1, int(budgets.scan_seconds * 1000))),
                            True,
                        )
                    )
                )
                session.execute(
                    select(
                        func.set_config(
                            "lock_timeout", str(budgets.lock_timeout_ms), True
                        )
                    )
                )
                service = get_analysis_lifecycle_service(session, gateway)
                yield PublishedVersionReader(
                    SqlAlchemyPublishedArchitectureSource(session), service.get_analysis
                )

    return DeliveryCoordinator(
        engine=engine,
        registry=registry if registry is not None else get_delivery_handler_registry(),
        publisher=CeleryDeliveryPublisher(
            app,
            queue=fleet.queue,
            timeout_seconds=budgets.broker_timeout_seconds,
            hard_timeout_seconds=budgets.execution_seconds
            + budgets.lease_seconds
            + budgets.publication_seconds,
        ),
        policy=policy,
        budgets=budgets,
        fleet=fleet,
        reader=reader,
        dispatch_enabled=settings.delivery_dispatch_enabled
        and settings.delivery_operational_approval,
        execution_enabled=settings.delivery_operational_approval,
        manual_retry_policy=(
            ManualRetryPolicy.model_validate_json(settings.delivery_manual_retry_json)
            if settings.delivery_manual_retry_json
            and settings.delivery_operational_approval
            else None
        ),
    )


def get_delivery_reader() -> Iterator[PublishedVersionReader]:
    """Public read providers; no producer/output-module imports."""
    from backend.platform.config import get_settings
    from backend.platform.dependency_injection import get_database_engine

    settings = get_settings()
    with contextmanager(get_platform_repository_gateway)(settings) as gateway:
        with Session(get_database_engine(), autoflush=False) as session:
            yield PublishedVersionReader(
                SqlAlchemyPublishedArchitectureSource(session),
                get_analysis_lifecycle_service(session, gateway).get_analysis,
            )


def build_attempt_retirement_reader(
    engine: Engine, budgets: RuntimeBudgets
) -> AttemptRetirementReader:
    """Inject the public port into producer cleanup; no private M1 tables needed."""
    budgets = RuntimeBudgets.model_validate(budgets)
    return SqlAlchemyAttemptRetirementReader(
        engine,
        timeout_seconds=budgets.publication_seconds,
        lock_timeout_ms=budgets.lock_timeout_ms,
    )
