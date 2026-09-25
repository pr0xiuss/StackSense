"""Version 1 StackSense API router."""

from fastapi import APIRouter

from backend.api.v1.project_access import router as project_access_router
from backend.api.v1.projects import router as projects_router
from backend.api.v1.repositories import router as repositories_router
from backend.api.v1.root import router as root_router
from backend.api.v1.system import router as system_router
from backend.platform.health import router as health_router

router = APIRouter(prefix="/api/v1")

router.include_router(root_router)
router.include_router(health_router)
router.include_router(system_router)
router.include_router(projects_router)
router.include_router(project_access_router)
router.include_router(repositories_router)
