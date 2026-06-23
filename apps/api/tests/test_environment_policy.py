import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.core.config import Settings
from passport_auth.main import create_app
from passport_auth.setup.store import DashboardSettings, InMemorySetupStore

STRONG_ENCRYPTION_KEY = "environment-policy-encryption-key-32"
STRONG_DASHBOARD_JWT_SECRET = "environment-policy-dashboard-jwt32"
STRONG_PUBLIC_JWT_SECRET = "environment-policy-public-jwt-key32"


def create_app_with_environment(app_env: str) -> object:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    setup_store.save_dashboard_settings(
        DashboardSettings(
            allowed_origins=("https://app.example.com",),
            redirect_urls=("https://app.example.com/auth/callback",),
            password_login_enabled=True,
        )
    )
    return create_app(
        settings=Settings(
            app_encryption_key=STRONG_ENCRYPTION_KEY,
            app_env=app_env,
            dashboard_jwt_secret=STRONG_DASHBOARD_JWT_SECRET,
            public_jwt_secret=STRONG_PUBLIC_JWT_SECRET,
        ),
        setup_store=setup_store,
    )


@pytest.mark.asyncio
async def test_development_cors_allows_localhost_http_origins_with_ports() -> None:
    transport = ASGITransport(app=create_app_with_environment("development"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.options(
            "/api/v1/auth/register",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.asyncio
async def test_development_cors_allows_127_0_0_1_http_origins_with_ports() -> None:
    transport = ASGITransport(app=create_app_with_environment("development"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.options(
            "/api/v1/auth/register",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


@pytest.mark.asyncio
async def test_production_cors_rejects_unconfigured_localhost_origins() -> None:
    transport = ASGITransport(app=create_app_with_environment("production"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.options(
            "/api/v1/auth/register",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code != 204
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_development_redirect_validation_allows_localhost_http_callback() -> None:
    verifier = "correct horse battery staple public verifier"
    transport = ASGITransport(app=create_app_with_environment("development"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Dev User",
                "email": "dev@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "http://localhost:5173/auth/callback",
                "code_challenge": verifier,
            },
        )

    assert response.status_code == 200
    assert response.json()["sent"] is True
    assert len(response.json()["dev_otp"]) == 6


@pytest.mark.asyncio
async def test_production_redirect_validation_rejects_unconfigured_localhost_callback() -> None:
    verifier = "correct horse battery staple public verifier"
    transport = ASGITransport(app=create_app_with_environment("production"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Dev User",
                "email": "dev@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "http://localhost:5173/auth/callback",
                "code_challenge": verifier,
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Redirect URL is not allowed.")
    assert "http://localhost:5173/auth/callback" in response.json()["detail"]
    assert "https://app.example.com/auth/callback" in response.json()["detail"]
