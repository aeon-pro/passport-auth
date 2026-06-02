import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.core.config import Settings
from passport_auth.main import create_app
from passport_auth.setup.store import (
    DashboardSettings,
    InMemorySetupStore,
    dashboard_settings_from_storage_dict,
    dashboard_settings_to_storage_dict,
)


async def login_owner(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/dashboard/auth/login",
        json={
            "email": "owner@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    return str(response.json()["access_token"])


def create_test_app() -> object:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    return create_app(
        settings=Settings(app_encryption_key="test-jwt-secret"),
        setup_store=setup_store,
    )


@pytest.mark.asyncio
async def test_dashboard_settings_require_owner_token() -> None:
    transport = ASGITransport(app=create_test_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/dashboard/settings")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_settings_return_defaults() -> None:
    transport = ASGITransport(app=create_test_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        response = await client.get(
            "/api/v1/dashboard/settings",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "app_domain": "",
        "auth_domain": "",
        "allowed_origins": [],
        "redirect_urls": [],
        "resend_from_email": "",
        "resend_configured": False,
        "google_client_id": "",
        "google_configured": False,
        "brand_name": "Passport Auth",
        "primary_color": "#f5f5f7",
        "password_login_enabled": True,
        "otp_login_enabled": False,
        "magic_link_enabled": False,
        "google_oauth_enabled": False,
        "password_reset_otp_enabled": True,
    }


@pytest.mark.asyncio
async def test_dashboard_settings_save_config_without_exposing_secrets() -> None:
    transport = ASGITransport(app=create_test_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        headers = {"Authorization": f"Bearer {token}"}
        save_response = await client.put(
            "/api/v1/dashboard/settings",
            headers=headers,
            json={
                "app_domain": "app.example.com",
                "auth_domain": "auth.example.com",
                "allowed_origins": [
                    "https://app.example.com",
                    "https://admin.example.com",
                ],
                "redirect_urls": ["https://app.example.com/auth/callback"],
                "resend_from_email": "Passport Auth <auth@example.com>",
                "resend_api_key": "re_secret_key",
                "google_client_id": "google-client-id",
                "google_client_secret": "google-client-secret",
                "brand_name": "Acme Auth",
                "primary_color": "#ffffff",
                "password_login_enabled": True,
                "otp_login_enabled": True,
                "magic_link_enabled": True,
                "google_oauth_enabled": True,
                "password_reset_otp_enabled": False,
            },
        )
        read_response = await client.get("/api/v1/dashboard/settings", headers=headers)

    assert save_response.status_code == 200
    assert read_response.status_code == 200
    assert read_response.json() == {
        "app_domain": "app.example.com",
        "auth_domain": "auth.example.com",
        "allowed_origins": [
            "https://app.example.com",
            "https://admin.example.com",
        ],
        "redirect_urls": ["https://app.example.com/auth/callback"],
        "resend_from_email": "Passport Auth <auth@example.com>",
        "resend_configured": True,
        "google_client_id": "google-client-id",
        "google_configured": True,
        "brand_name": "Acme Auth",
        "primary_color": "#ffffff",
        "password_login_enabled": True,
        "otp_login_enabled": True,
        "magic_link_enabled": True,
        "google_oauth_enabled": True,
        "password_reset_otp_enabled": False,
    }
    assert "re_secret_key" not in read_response.text
    assert "google-client-secret" not in read_response.text


def test_dashboard_setting_secrets_are_encrypted_for_storage() -> None:
    settings = DashboardSettings(
        resend_api_key="re_secret_key",
        google_client_secret="google-client-secret",
    )

    stored = dashboard_settings_to_storage_dict(settings, encryption_key="test-secret")
    loaded = dashboard_settings_from_storage_dict(stored, encryption_key="test-secret")

    assert stored["resend_api_key"] != "re_secret_key"
    assert stored["google_client_secret"] != "google-client-secret"
    assert str(stored["resend_api_key"]).startswith("fernet:")
    assert str(stored["google_client_secret"]).startswith("fernet:")
    assert loaded.resend_api_key == "re_secret_key"
    assert loaded.google_client_secret == "google-client-secret"
