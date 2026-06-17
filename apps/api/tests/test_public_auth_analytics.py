import base64
import hashlib

import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.analytics import ClickHouseAnalyticsSink, NoopAnalyticsSink
from passport_auth.auth.store import InMemoryAuthStore
from passport_auth.core.config import Settings
from passport_auth.main import create_app
from passport_auth.setup.store import DashboardSettings, InMemorySetupStore


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class RecordingAnalyticsSink:
    def __init__(self) -> None:
        self.events = []

    def record_public_auth_event(self, event) -> None:
        self.events.append(event)


def create_password_login_app(
    *,
    app_env: str,
    redirect_url: str,
    allowed_origin: str,
    analytics_sink: RecordingAnalyticsSink,
):
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    setup_store.save_dashboard_settings(
        DashboardSettings(
            app_domain="app.example.com",
            auth_domain="auth.example.com",
            allowed_origins=(allowed_origin,),
            redirect_urls=(redirect_url,),
            brand_name="Acme Auth",
            password_login_enabled=True,
        )
    )
    auth_store = InMemoryAuthStore()
    auth_store.create_user(
        email="user@example.com",
        name="User Example",
        password="correct-horse-battery-staple",
    )
    app = create_app(
        settings=Settings(
            app_encryption_key="test-public-auth-analytics-secret",
            app_env=app_env,
        ),
        setup_store=setup_store,
        auth_store=auth_store,
        analytics_sink=analytics_sink,
    )
    return app


def test_default_analytics_sink_is_clickhouse_only_in_production() -> None:
    setup_store = InMemorySetupStore()
    auth_store = InMemoryAuthStore()

    production_app = create_app(
        settings=Settings(
            app_env="production",
            app_encryption_key="test-public-auth-analytics-secret",
            clickhouse_url="http://clickhouse:8123/passport_auth",
        ),
        setup_store=setup_store,
        auth_store=auth_store,
    )
    development_app = create_app(
        settings=Settings(
            app_env="development",
            app_encryption_key="test-public-auth-analytics-secret",
            clickhouse_url="http://clickhouse:8123/passport_auth",
        ),
        setup_store=setup_store,
        auth_store=auth_store,
    )

    assert isinstance(production_app.state.analytics_sink, ClickHouseAnalyticsSink)
    assert isinstance(development_app.state.analytics_sink, NoopAnalyticsSink)


@pytest.mark.asyncio
async def test_production_https_public_auth_records_clickhouse_events_only() -> None:
    analytics_sink = RecordingAnalyticsSink()
    verifier = "correct horse battery staple analytics verifier"
    redirect_url = "https://app.example.com/auth/callback"
    app = create_password_login_app(
        app_env="production",
        redirect_url=redirect_url,
        allowed_origin="https://app.example.com",
        analytics_sink=analytics_sink,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login_response = await client.post(
            "/api/v1/auth/password/login",
            headers={"Origin": "https://app.example.com"},
            json={
                "email": "user@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": redirect_url,
                "code_challenge": pkce_challenge(verifier),
            },
        )
        token_response = await client.post(
            "/api/v1/auth/token",
            headers={"Origin": "https://app.example.com"},
            json={
                "code": login_response.json()["authorization_code"],
                "code_verifier": verifier,
            },
        )

    assert login_response.status_code == 200
    assert token_response.status_code == 200
    assert [event.event_type for event in analytics_sink.events] == [
        "login_success",
        "token_exchange",
    ]
    assert analytics_sink.events[0].auth_method == "password"
    assert analytics_sink.events[0].redirect_url == redirect_url
    assert analytics_sink.events[1].user_id == token_response.json()["user"]["id"]


@pytest.mark.asyncio
async def test_local_and_http_urls_do_not_record_public_auth_analytics() -> None:
    verifier = "correct horse battery staple analytics verifier"

    http_sink = RecordingAnalyticsSink()
    http_app = create_password_login_app(
        app_env="production",
        redirect_url="http://localhost:5173/auth/callback",
        allowed_origin="http://localhost:5173",
        analytics_sink=http_sink,
    )
    http_transport = ASGITransport(app=http_app)

    async with AsyncClient(transport=http_transport, base_url="http://testserver") as client:
        http_response = await client.post(
            "/api/v1/auth/password/login",
            headers={"Origin": "http://localhost:5173"},
            json={
                "email": "user@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "http://localhost:5173/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )

    development_sink = RecordingAnalyticsSink()
    development_app = create_password_login_app(
        app_env="development",
        redirect_url="https://app.example.com/auth/callback",
        allowed_origin="https://app.example.com",
        analytics_sink=development_sink,
    )
    development_transport = ASGITransport(app=development_app)

    async with AsyncClient(transport=development_transport, base_url="http://testserver") as client:
        development_response = await client.post(
            "/api/v1/auth/password/login",
            headers={"Origin": "https://app.example.com"},
            json={
                "email": "user@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )

    assert http_response.status_code == 200
    assert development_response.status_code == 200
    assert http_sink.events == []
    assert development_sink.events == []
