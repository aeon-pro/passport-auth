import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.core.config import Settings
from passport_auth.main import create_app
from passport_auth.setup.store import InMemorySetupStore


def create_test_app() -> tuple[InMemorySetupStore, object]:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    app = create_app(
        settings=Settings(app_encryption_key="test-jwt-secret"),
        setup_store=setup_store,
    )
    return setup_store, app


def create_test_app_with_settings(settings: Settings) -> tuple[InMemorySetupStore, object]:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    app = create_app(settings=settings, setup_store=setup_store)
    return setup_store, app


@pytest.mark.asyncio
async def test_owner_can_login_and_read_dashboard_profile() -> None:
    _, app = create_test_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login_response = await client.post(
            "/api/v1/dashboard/auth/login",
            json={
                "email": "owner@example.com",
                "password": "correct-horse-battery-staple",
            },
        )
        token = login_response.json()["access_token"]
        me_response = await client.get(
            "/api/v1/dashboard/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"
    assert login_response.json()["user"] == {"email": "owner@example.com", "role": "owner"}
    assert me_response.status_code == 200
    assert me_response.json() == {"email": "owner@example.com", "role": "owner"}


@pytest.mark.asyncio
async def test_dashboard_profile_requires_valid_bearer_token() -> None:
    _, app = create_test_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        missing_response = await client.get("/api/v1/dashboard/auth/me")
        invalid_response = await client.get(
            "/api/v1/dashboard/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert missing_response.status_code == 401
    assert invalid_response.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_wrong_password() -> None:
    _, app = create_test_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/dashboard/auth/login",
            json={"email": "owner@example.com", "password": "wrong-password"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


@pytest.mark.asyncio
async def test_password_reset_otp_updates_owner_password() -> None:
    _, app = create_test_app_with_settings(
        Settings(app_encryption_key="test-jwt-secret", app_env="local")
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        start_response = await client.post(
            "/api/v1/dashboard/auth/password-reset/start",
            json={"email": "owner@example.com"},
        )
        otp = start_response.json()["dev_otp"]
        confirm_response = await client.post(
            "/api/v1/dashboard/auth/password-reset/confirm",
            json={
                "email": "owner@example.com",
                "otp": otp,
                "password": "new-correct-horse-battery-staple",
            },
        )
        old_login_response = await client.post(
            "/api/v1/dashboard/auth/login",
            json={
                "email": "owner@example.com",
                "password": "correct-horse-battery-staple",
            },
        )
        new_login_response = await client.post(
            "/api/v1/dashboard/auth/login",
            json={
                "email": "owner@example.com",
                "password": "new-correct-horse-battery-staple",
            },
        )

    assert start_response.status_code == 200
    assert start_response.json()["sent"] is True
    assert len(otp) == 6
    assert confirm_response.status_code == 200
    assert confirm_response.json() == {"ok": True}
    assert old_login_response.status_code == 401
    assert new_login_response.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_otp_can_be_disabled() -> None:
    _, app = create_test_app_with_settings(
        Settings(
            app_encryption_key="test-jwt-secret",
            password_reset_otp_enabled=False,
        )
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/dashboard/auth/password-reset/start",
            json={"email": "owner@example.com"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Password reset is disabled."}
