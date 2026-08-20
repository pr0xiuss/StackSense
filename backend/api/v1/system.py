"""Version 1 system endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.platform.config import get_settings
from backend.platform.dependency_injection import get_database_session

router = APIRouter(prefix="/system", tags=["system"])


class DatabaseStatusResponse(BaseModel):
    """Database connectivity response."""

    status: str


@router.get("/info")
async def system_info() -> dict[str, str]:
    """Return basic StackSense system information."""
    settings = get_settings()

    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@router.get("/database", response_model=DatabaseStatusResponse)
def database_status(
    session: Session = Depends(get_database_session),
) -> DatabaseStatusResponse:
    """Verify that StackSense can communicate with PostgreSQL."""
    session.execute(text("SELECT 1"))

    return DatabaseStatusResponse(status="connected")
