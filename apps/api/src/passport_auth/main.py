from pathlib import Path

from fastapi import FastAPI, Request
from starlette.responses import Response

from passport_auth.api.v1 import router as api_v1_router
from passport_auth.auth.email import AuthEmailSender, ResendEmailSender
from passport_auth.auth.google import GoogleOAuthClient, UrlLibGoogleOAuthClient
from passport_auth.auth.store import AuthStore, create_auth_store
from passport_auth.core.config import Settings, get_settings
from passport_auth.setup.store import SetupStore, create_setup_store
from passport_auth.web.static import mount_dashboard, mount_dashboard_assets


def create_app(
    *,
    settings: Settings | None = None,
    setup_store: SetupStore | None = None,
    auth_store: AuthStore | None = None,
    auth_email_sender: AuthEmailSender | None = None,
    google_oauth_client: GoogleOAuthClient | None = None,
    static_dir: str | Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Passport Auth API")

    resolved_settings = settings or get_settings()
    app.state.settings = resolved_settings
    app.state.setup_store = setup_store or create_setup_store(
        resolved_settings.database_url,
        encryption_key=resolved_settings.app_encryption_key,
    )
    app.state.auth_store = auth_store or create_auth_store(resolved_settings.database_url)
    app.state.auth_email_sender = auth_email_sender or ResendEmailSender()
    app.state.google_oauth_client = google_oauth_client or UrlLibGoogleOAuthClient()
    install_dynamic_cors(app)
    app.include_router(api_v1_router)
    mount_dashboard_assets(app, resolved_settings.dashboard_asset_dir)

    dashboard_static_dir = static_dir or resolved_settings.web_static_dir
    if dashboard_static_dir:
        mount_dashboard(app, dashboard_static_dir)

    return app


def install_dynamic_cors(app: FastAPI) -> None:
    @app.middleware("http")
    async def dynamic_dashboard_cors(request: Request, call_next):
        origin = request.headers.get("Origin")
        is_api_request = request.url.path.startswith("/api/")
        is_preflight = request.method == "OPTIONS" and bool(
            request.headers.get("Access-Control-Request-Method")
        )

        allowed_origins = app.state.setup_store.get_dashboard_settings().allowed_origins
        if is_api_request and origin and origin in allowed_origins:
            response = Response(status_code=204) if is_preflight else await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, X-Requested-With"
            )
            response.headers["Access-Control-Max-Age"] = "600"
            return response

        return await call_next(request)


app = create_app()
