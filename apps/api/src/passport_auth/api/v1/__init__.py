from fastapi import APIRouter

from passport_auth.api.v1.dashboard_auth import router as dashboard_auth_router
from passport_auth.api.v1.health import router as health_router
from passport_auth.api.v1.setup import router as setup_router

router = APIRouter(prefix="/api/v1")
router.include_router(dashboard_auth_router)
router.include_router(health_router)
router.include_router(setup_router)
