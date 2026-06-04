from fastapi import APIRouter

from passport_auth.api.v1.auth import router as auth_router
from passport_auth.api.v1.dashboard_assets import router as dashboard_assets_router
from passport_auth.api.v1.dashboard_auth import router as dashboard_auth_router
from passport_auth.api.v1.dashboard_settings import router as dashboard_settings_router
from passport_auth.api.v1.health import router as health_router
from passport_auth.api.v1.setup import router as setup_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(dashboard_assets_router)
router.include_router(dashboard_auth_router)
router.include_router(dashboard_settings_router)
router.include_router(health_router)
router.include_router(setup_router)
