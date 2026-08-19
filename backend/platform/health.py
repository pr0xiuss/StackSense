"""Application health and readiness endpoints."""

from fastapi import APIRouter

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Report whether the application process is alive."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness() -> dict[str, str]:
    """Report whether the application is ready to receive requests."""
    return {"status": "ready"}