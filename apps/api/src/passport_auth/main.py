from pathlib import Path

from fastapi import FastAPI

from passport_auth.api.v1 import router as api_v1_router
from passport_auth.core.config import Settings, get_settings
from passport_auth.web.static import mount_dashboard


def create_app(
    *,
    settings: Settings | None = None,
    static_dir: str | Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Passport Auth API")
    app.include_router(api_v1_router)

    resolved_settings = settings or get_settings()
    dashboard_static_dir = static_dir or resolved_settings.web_static_dir
    if dashboard_static_dir:
        mount_dashboard(app, dashboard_static_dir)

    return app


app = create_app()
