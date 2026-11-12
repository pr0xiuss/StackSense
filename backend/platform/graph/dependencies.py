"""P4-owned graph infrastructure composition providers."""

from datetime import timedelta
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.platform.config import Settings
from backend.platform.dependency_injection import (
    get_application_settings,
    get_database_session,
)
from backend.platform.graph.executor import ProjectionExecutor
from backend.platform.graph.health import GraphHealthService
from backend.platform.graph.lifecycle import GraphProjectionLifecycle
from backend.platform.graph.neo4j import Neo4jInfrastructure
from backend.platform.graph.persistence import (
    GraphProjectionResourceModel,
    GraphRuntimeCapabilityModel,
    SqlAlchemyGraphProjectionRepository,
)
from backend.platform.graph.projection_store import (
    Neo4jProjectionStore,
    ProjectionStore,
)
from backend.platform.graph.repository import GraphProjectionRepository
from backend.platform.graph.runtime import (
    PROJECTION_EXECUTION,
    RECONCILIATION_SCHEDULING,
    GraphRuntimeCapabilities,
)
from backend.platform.graph.source import (
    PublishedArchitectureSource,
    SqlAlchemyPublishedArchitectureSource,
)
from backend.platform.graph.verification import GraphVerifier


def get_graph_health_service(
    settings: Settings = Depends(get_application_settings),
    session: Session = Depends(get_database_session),
) -> GraphHealthService:
    """Provide graph health without modifying frozen analysis composition."""
    lifecycle_ready = False
    try:
        session.execute(select(GraphProjectionResourceModel.id).limit(1))
        session.execute(select(GraphRuntimeCapabilityModel.capability).limit(1))
        lifecycle_ready = True
    except SQLAlchemyError:
        session.rollback()

    def broker_probe() -> None:
        from backend.worker.celery_app import celery_app

        with celery_app.connection_for_read() as connection:
            connection.ensure_connection(
                max_retries=0,
                timeout=settings.graph_broker_health_timeout_seconds,
            )

    scheduling_ready = False
    execution_ready = False
    if lifecycle_ready:
        runtime = GraphRuntimeCapabilities(session)
        ttl = timedelta(seconds=settings.graph_capability_ttl_seconds)
        scheduling_ready = runtime.is_live(RECONCILIATION_SCHEDULING, ttl=ttl)
        execution_ready = (
            settings.graph_projection_dispatch_enabled
            and runtime.is_live(PROJECTION_EXECUTION, ttl=ttl)
        )
    return GraphHealthService(
        settings,
        lifecycle_ready=lifecycle_ready,
        broker_probe=broker_probe,
        scheduling_registered=scheduling_ready,
        projection_execution_ready=execution_ready,
    )


def get_graph_projection_repository(
    session: Session = Depends(get_database_session),
) -> GraphProjectionRepository:
    """Provide the PostgreSQL lifecycle adapter in the request transaction."""
    return SqlAlchemyGraphProjectionRepository(session)


def get_published_architecture_source(
    session: Session = Depends(get_database_session),
) -> PublishedArchitectureSource:
    """Provide the P4-owned read adapter over frozen Architecture Versions."""
    return SqlAlchemyPublishedArchitectureSource(session)


def get_graph_projection_lifecycle(
    repository: GraphProjectionRepository = Depends(get_graph_projection_repository),
) -> GraphProjectionLifecycle:
    """Provide lifecycle orchestration without modifying P3 composition."""
    return GraphProjectionLifecycle(repository)


@lru_cache
def get_neo4j_infrastructure(
    settings: Settings = Depends(get_application_settings),
) -> Neo4jInfrastructure:
    """Provide cached Neo4j infrastructure adapter."""
    return Neo4jInfrastructure(settings)


def get_projection_store(
    settings: Settings = Depends(get_application_settings),
    infra: Neo4jInfrastructure = Depends(get_neo4j_infrastructure),
) -> ProjectionStore:
    """Provide bounded Neo4j projection store."""
    return Neo4jProjectionStore(infra.driver, settings)


def get_graph_verifier(
    store: ProjectionStore = Depends(get_projection_store),
) -> GraphVerifier:
    """Provide independent candidate graph verifier."""
    return GraphVerifier(store=store)


def get_projection_executor(
    settings: Settings = Depends(get_application_settings),
    store: ProjectionStore = Depends(get_projection_store),
    verifier: GraphVerifier = Depends(get_graph_verifier),
) -> ProjectionExecutor:
    """Provide P4-W1 projection execution coordinator."""
    return ProjectionExecutor(
        settings=settings,
        store=store,
        verifier=verifier,
    )
