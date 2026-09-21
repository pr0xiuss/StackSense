"""Version 1 API metadata endpoint."""

from fastapi import APIRouter

from backend.api.v1.schemas import ApiMetadataResponse
from backend.platform.config import get_settings

router = APIRouter()


@router.get("/", response_model=ApiMetadataResponse)
async def api_root() -> ApiMetadataResponse:
    """Return basic API metadata."""
    settings = get_settings()

    return ApiMetadataResponse(
        name=settings.app_name,
        version=settings.app_version,
    )
