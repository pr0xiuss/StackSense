"""StackSense health endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Report whether the application is ready to receive requests."""
    return {"status": "ready"}
