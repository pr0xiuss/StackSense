"""Layered graph infrastructure health model and service."""

from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from backend.platform.config import Settings
from backend.platform.graph.neo4j import (
    GraphConfigurationError,
    GraphDependencyUnavailableError,
    GraphInfrastructure,
    GraphSchemaCompatibilityError,
    Neo4jInfrastructure,
)


class GraphHealthStatus(StrEnum):
    """Public graph infrastructure health vocabulary."""

    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class GraphCapabilityStatus(StrEnum):
    """Internal capability readiness separate from public lifecycle state."""

    READY = "ready"
    NOT_READY = "not_ready"


class GraphComponentHealth(BaseModel):
    """Safe health summary for one graph dependency."""

    model_config = ConfigDict(frozen=True)

    status: GraphHealthStatus
    code: str


class GraphCapabilities(BaseModel):
    """Capabilities that intentionally arrive in later M1/M2 batches."""

    model_config = ConfigDict(frozen=True)

    lifecycle_persistence: GraphCapabilityStatus
    reconciliation_scheduling: GraphCapabilityStatus
    projection_execution: GraphCapabilityStatus


class GraphHealthResponse(BaseModel):
    """Graph-specific health response; independent from core readiness."""

    model_config = ConfigDict(frozen=True)

    status: GraphHealthStatus
    components: dict[str, GraphComponentHealth]
    capabilities: GraphCapabilities


GraphInfrastructureFactory = Callable[[Settings], GraphInfrastructure]
BrokerProbe = Callable[[], None]


class GraphHealthService:
    """Evaluate graph infrastructure without affecting core application health."""

    def __init__(
        self,
        settings: Settings,
        *,
        infrastructure_factory: GraphInfrastructureFactory = Neo4jInfrastructure,
        lifecycle_ready: bool = False,
        broker_probe: BrokerProbe | None = None,
        scheduling_registered: bool = False,
        projection_execution_ready: bool = False,
    ) -> None:
        self._settings = settings
        self._infrastructure_factory = infrastructure_factory
        self._lifecycle_ready = lifecycle_ready
        self._broker_probe = broker_probe
        self._scheduling_registered = scheduling_registered
        self._projection_execution_ready = projection_execution_ready

    def check(self) -> GraphHealthResponse:
        """Return a sanitized graph infrastructure and capability summary."""
        infrastructure: GraphInfrastructure | None = None
        status = GraphHealthStatus.READY
        code = "connected"
        try:
            infrastructure = self._infrastructure_factory(self._settings)
            infrastructure.initialize()
        except GraphSchemaCompatibilityError:
            status = GraphHealthStatus.UNAVAILABLE
            code = "schema_incompatible"
        except GraphConfigurationError:
            status = GraphHealthStatus.UNAVAILABLE
            code = "configuration_invalid"
        except GraphDependencyUnavailableError:
            status = GraphHealthStatus.DEGRADED
            code = "dependency_unreachable"
        finally:
            if infrastructure is not None:
                infrastructure.close()

        components = {"neo4j": GraphComponentHealth(status=status, code=code)}
        lifecycle_status = (
            GraphHealthStatus.READY
            if self._lifecycle_ready
            else GraphHealthStatus.UNAVAILABLE
        )
        components["postgresql"] = GraphComponentHealth(
            status=lifecycle_status,
            code="connected" if self._lifecycle_ready else "lifecycle_unavailable",
        )
        if not self._lifecycle_ready:
            status = GraphHealthStatus.UNAVAILABLE
        broker_ready = False
        broker_status = GraphHealthStatus.DEGRADED
        broker_code = "probe_unavailable"
        if self._broker_probe is not None:
            try:
                self._broker_probe()
                broker_ready = True
                broker_status = GraphHealthStatus.READY
                broker_code = "connected"
            except Exception:
                broker_code = "dependency_unreachable"
        components["rabbitmq"] = GraphComponentHealth(
            status=broker_status, code=broker_code
        )
        if status is GraphHealthStatus.READY and not broker_ready:
            status = GraphHealthStatus.DEGRADED
        scheduling_ready = (
            self._lifecycle_ready and broker_ready and self._scheduling_registered
        )
        execution_ready = scheduling_ready and self._projection_execution_ready

        return GraphHealthResponse(
            status=status,
            components=components,
            capabilities=GraphCapabilities(
                lifecycle_persistence=(
                    GraphCapabilityStatus.READY
                    if self._lifecycle_ready
                    else GraphCapabilityStatus.NOT_READY
                ),
                reconciliation_scheduling=(
                    GraphCapabilityStatus.READY
                    if scheduling_ready
                    else GraphCapabilityStatus.NOT_READY
                ),
                projection_execution=(
                    GraphCapabilityStatus.READY
                    if execution_ready
                    else GraphCapabilityStatus.NOT_READY
                ),
            ),
        )
