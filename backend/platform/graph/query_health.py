"""M3 query capability probe and health response model.

This module provides an independent health probe and response DTO for the
Phase 4 Module 3 graph query engine, separate from the frozen M1 lifecycle
health contracts.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from backend.platform.config import Settings
from backend.platform.graph.neo4j import (
    GRAPH_SCHEMA_VERSION,
    GraphConfigurationError,
    GraphDependencyUnavailableError,
    GraphSchemaCompatibilityError,
    Neo4jInfrastructure,
)


class GraphQueryHealthStatus(StrEnum):
    """Query engine health status vocabulary."""

    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class GraphQueryHealthResponse(BaseModel):
    """Independent query engine health check result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: GraphQueryHealthStatus
    code: str
    details: dict[str, Any] | None = None


class GraphQueryHealthProbe:
    """Evaluate query capability without mutating database or lifecycle state."""

    def __init__(
        self,
        settings: Settings,
        *,
        infrastructure_factory: Callable[[Settings], Neo4jInfrastructure] = (
            Neo4jInfrastructure
        ),
    ) -> None:
        self._settings = settings
        self._infrastructure_factory = infrastructure_factory

    def check(self) -> GraphQueryHealthResponse:
        """Probe query infrastructure and return a safe health response."""
        status = GraphQueryHealthStatus.READY
        code = "query_engine_ready"
        details: dict[str, Any] | None = None
        infrastructure: Neo4jInfrastructure | None = None

        try:
            infrastructure = self._infrastructure_factory(self._settings)
            capability = infrastructure.initialize()
            if capability.graph_schema_version != GRAPH_SCHEMA_VERSION:
                raise GraphSchemaCompatibilityError(
                    "Graph query schema version is incompatible."
                )
        except GraphSchemaCompatibilityError as exc:
            status = GraphQueryHealthStatus.UNAVAILABLE
            code = "graph_schema_incompatible"
            details = {"reason": str(exc)}
        except GraphConfigurationError as exc:
            status = GraphQueryHealthStatus.UNAVAILABLE
            code = "configuration_invalid"
            details = {"reason": str(exc)}
        except GraphDependencyUnavailableError as exc:
            status = GraphQueryHealthStatus.UNAVAILABLE
            code = "storage_unavailable"
            details = {"reason": str(exc)}
        except Exception as exc:
            status = GraphQueryHealthStatus.UNAVAILABLE
            code = "storage_probe_failed"
            details = {"error_type": exc.__class__.__name__}
        finally:
            if infrastructure is not None:
                infrastructure.close()

        return GraphQueryHealthResponse(
            status=status,
            code=code,
            details=details,
        )


__all__ = [
    "GraphQueryHealthProbe",
    "GraphQueryHealthResponse",
    "GraphQueryHealthStatus",
]
