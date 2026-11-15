"""StackSense core and graph-component health endpoints."""

from fastapi import APIRouter, Depends

from backend.platform.graph.dependencies import get_graph_health_service
from backend.platform.graph.health import GraphHealthResponse, GraphHealthService

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Report whether the application is ready to receive requests."""
    return {"status": "ready"}


@router.get("/health/graph", response_model=GraphHealthResponse)
def graph_health(
    service: GraphHealthService = Depends(get_graph_health_service),
) -> GraphHealthResponse:
    """Report graph health without changing core application readiness."""
    return service.check()
