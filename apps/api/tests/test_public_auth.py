import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.auth.store import InMemoryAuthStore
from passport_auth.core.config import Settings
from passport_auth.main import create_app
from passport_auth.setup.store import DashboardSettings, InMemorySetupStore


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class RecordingEmailSender:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    def send_template(
        self,
        *,
        template_key: str,
        to_email: str,
        values: dict[str, str],
        settings: DashboardSettings,
    ) -> None:
        self.messages.append(
            {
                "template_key": template_key,
                "to_email": to_email,
                "values": values,
                "brand_name": settings.brand_name,
            }
        )


class FakeGoogleOAuthClient:
    def authorization_url(self, *, state: str, settings: DashboardSettings) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}&client_id={settings.google_client_id}"

    def exchange_code(self, *, code: str, settings: DashboardSettings) -> dict[str, str]:
        assert code == "google-provider-code"
        assert settings.google_client_secret == "google-secret"
        return {"email": "google@example.com", "name": "Google User"}


def create_public_auth_app() -> tuple[InMemoryAuthStore, RecordingEmailSender, object]:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    setup_store.save_dashboard_settings(
        DashboardSettings(
            app_domain="app.example.com",
            auth_domain="auth.example.com",
            allowed_origins=("https://app.example.com",),
            redirect_urls=("https://app.example.com/auth/callback",),
            resend_from_email="Passport Auth <auth@example.com>",
            resend_api_key="re_test_key",
            google_client_id="google-client-id",
            google_client_secret="google-secret",
            brand_name="Acme Auth",
            password_login_enabled=True,
            otp_login_enabled=True,
            magic_link_enabled=True,
            google_oauth_enabled=True,
        )
    )
    auth_store = InMemoryAuthStore()
    email_sender = RecordingEmailSender()
    app = create_app(
        settings=Settings(app_encryption_key="test-public-auth-secret", app_env="local"),
        setup_store=setup_store,
        auth_store=auth_store,
        auth_email_sender=email_sender,
        google_oauth_client=FakeGoogleOAuthClient(),
    )
    return auth_store, email_sender, app


async def register_verified_user(
    client: AsyncClient,
    *,
    email: str,
    verifier: str,
    name: str = "Test User",
    password: str = "correct-horse-battery-staple",
    redirect_url: str = "https://app.example.com/auth/callback",
) -> dict[str, str]:
    start_response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "redirect_url": redirect_url,
            "code_challenge": pkce_challenge(verifier),
        },
    )
    verify_response = await client.post(
        "/api/v1/auth/register/verify",
        json={
            "email": email,
            "otp": start_response.json()["dev_otp"],
        },
    )
    assert start_response.status_code == 200
    assert verify_response.status_code == 200
    return verify_response.json()


@pytest.mark.asyncio
async def test_public_password_register_requires_email_otp_before_issuing_auth_code() -> None:
    verifier = "correct horse battery staple public verifier"
    _, email_sender, app = create_public_auth_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        register_start = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "  anurag  sharma ",
                "email": "user@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )
        invalid_verify = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": "user@example.com", "otp": "000000"},
        )
        verify_response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": "user@example.com", "otp": register_start.json()["dev_otp"]},
        )
        token_response = await client.post(
            "/api/v1/auth/token",
            json={
                "code": verify_response.json()["authorization_code"],
                "code_verifier": verifier,
            },
        )
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
        )

    assert register_start.status_code == 200
    assert register_start.json()["sent"] is True
    assert len(register_start.json()["dev_otp"]) == 6
    assert "authorization_code" not in register_start.json()
    assert email_sender.messages[-1]["template_key"] == "otp"
    assert invalid_verify.status_code == 400
    assert invalid_verify.json() == {"detail": "Invalid or expired registration code."}
    assert verify_response.status_code == 200
    assert verify_response.json()["redirect_url"] == "https://app.example.com/auth/callback"
    assert "authorization_code" in verify_response.json()
    assert token_response.status_code == 200
    assert token_response.json()["token_type"] == "bearer"
    assert token_response.json()["user"] == {
        "id": me_response.json()["id"],
        "name": "Anurag Sharma",
        "email": "user@example.com",
        "role": "user",
        "email_verified": True,
        "user_metadata": {},
    }
    assert token_response.json()["refresh_token"]
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"
    assert me_response.json()["name"] == "Anurag Sharma"


@pytest.mark.asyncio
async def test_public_auth_rejects_unknown_redirect_url() -> None:
    verifier = "correct horse battery staple public verifier"
    _, _, app = create_public_auth_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "User Example",
                "email": "user@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "https://evil.example.com/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Redirect URL is not allowed.")


@pytest.mark.asyncio
async def test_public_auth_request_validation_reports_redirect_url_mismatch() -> None:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    setup_store.save_dashboard_settings(
        DashboardSettings(
            app_domain="app.example.com",
            auth_domain="auth.example.com",
            allowed_origins=("https://app.example.com",),
            redirect_urls=("https://app.example.com/auth/callback",),
            resend_from_email="Passport Auth <auth@example.com>",
            brand_name="Acme Auth",
            password_login_enabled=True,
        )
    )
    app = create_app(
        settings=Settings(app_encryption_key="test-public-auth-secret", app_env="production"),
        setup_store=setup_store,
        auth_store=InMemoryAuthStore(),
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        allowed_response = await client.get(
            "/api/v1/auth/request/validate",
            params={
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": "x" * 43,
            },
        )
        rejected_response = await client.get(
            "/api/v1/auth/request/validate",
            params={
                "redirect_url": "http://localhost:5173/auth/callback",
                "code_challenge": "x" * 43,
            },
        )

    assert allowed_response.status_code == 200
    assert allowed_response.json() == {
        "ok": True,
        "redirect_url": "https://app.example.com/auth/callback",
    }
    assert rejected_response.status_code == 400
    assert "http://localhost:5173/auth/callback" in rejected_response.json()["detail"]
    assert "https://app.example.com/auth/callback" in rejected_response.json()["detail"]


@pytest.mark.asyncio
async def test_public_api_preflight_only_allows_configured_origins() -> None:
    _, _, app = create_public_auth_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        allowed_response = await client.options(
            "/api/v1/auth/register",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        denied_response = await client.options(
            "/api/v1/auth/register",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert allowed_response.status_code == 204
    assert allowed_response.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "Authorization" in allowed_response.headers["access-control-allow-headers"]
    assert denied_response.status_code != 204
    assert "access-control-allow-origin" not in denied_response.headers


@pytest.mark.asyncio
async def test_public_otp_and_magic_link_flows_send_email_and_issue_auth_codes() -> None:
    verifier = "correct horse battery staple public verifier"
    _, email_sender, app = create_public_auth_app()
    transport = ASGITransport(app=app)
    payload = {
        "email": "link@example.com",
        "redirect_url": "https://app.example.com/auth/callback",
        "code_challenge": pkce_challenge(verifier),
    }

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        otp_start = await client.post("/api/v1/auth/otp/start", json=payload)
        otp_verify = await client.post(
            "/api/v1/auth/otp/verify",
            json={**payload, "otp": otp_start.json()["dev_otp"]},
        )
        magic_start = await client.post("/api/v1/auth/magic-link/start", json=payload)
        magic_consume = await client.post(
            "/api/v1/auth/magic-link/consume",
            json={"token": magic_start.json()["dev_token"]},
        )

    assert otp_start.status_code == 200
    assert otp_start.json()["sent"] is True
    assert len(otp_start.json()["dev_otp"]) == 6
    assert otp_verify.status_code == 200
    assert "authorization_code" in otp_verify.json()
    assert magic_start.status_code == 200
    assert magic_start.json()["sent"] is True
    assert magic_start.json()["dev_magic_link"].startswith("/verify?token=")
    assert magic_consume.status_code == 200
    assert "authorization_code" in magic_consume.json()
    assert [message["template_key"] for message in email_sender.messages] == ["otp", "magic_link"]


@pytest.mark.asyncio
async def test_public_refresh_tokens_rotate_and_logout_revokes_current_token() -> None:
    verifier = "correct horse battery staple public verifier"
    _, _, app = create_public_auth_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        register_response = await register_verified_user(
            client,
            email="rotation@example.com",
            verifier=verifier,
        )
        token_response = await client.post(
            "/api/v1/auth/token",
            json={
                "code": register_response["authorization_code"],
                "code_verifier": verifier,
            },
        )
        first_refresh = token_response.json()["refresh_token"]
        rotated_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": first_refresh},
        )
        replay_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": first_refresh},
        )
        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": rotated_response.json()["refresh_token"]},
        )
        after_logout_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": rotated_response.json()["refresh_token"]},
        )

    assert rotated_response.status_code == 200
    assert rotated_response.json()["refresh_token"] != first_refresh
    assert replay_response.status_code == 401
    assert logout_response.status_code == 200
    assert logout_response.json() == {"ok": True}
    assert after_logout_response.status_code == 401


@pytest.mark.asyncio
async def test_public_password_reset_otp_updates_user_password() -> None:
    verifier = "correct horse battery staple public verifier"
    _, email_sender, app = create_public_auth_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await register_verified_user(
            client,
            email="reset-user@example.com",
            verifier=verifier,
        )
        reset_start = await client.post(
            "/api/v1/auth/password-reset/start",
            json={"email": "reset-user@example.com"},
        )
        reset_confirm = await client.post(
            "/api/v1/auth/password-reset/confirm",
            json={
                "email": "reset-user@example.com",
                "otp": reset_start.json()["dev_otp"],
                "password": "new-correct-horse-battery-staple",
            },
        )
        old_login = await client.post(
            "/api/v1/auth/password/login",
            json={
                "email": "reset-user@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )
        new_login = await client.post(
            "/api/v1/auth/password/login",
            json={
                "email": "reset-user@example.com",
                "password": "new-correct-horse-battery-staple",
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )

    assert reset_start.status_code == 200
    assert len(reset_start.json()["dev_otp"]) == 6
    assert reset_confirm.status_code == 200
    assert reset_confirm.json() == {"ok": True}
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert email_sender.messages[-1]["template_key"] == "password_reset"


@pytest.mark.asyncio
async def test_public_google_oauth_start_and_callback_issue_auth_code_with_google_name() -> None:
    auth_store, _, app = create_public_auth_app()
    auth_store.create_user(email="google@example.com")
    transport = ASGITransport(app=app)
    verifier = "correct horse battery staple public verifier"

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        start_response = await client.get(
            "/api/v1/auth/google/start",
            params={
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )
        authorization_url = start_response.json()["authorization_url"]
        state = parse_qs(urlparse(authorization_url).query)["state"][0]
        callback_response = await client.get(
            "/api/v1/auth/google/callback",
            params={"state": state, "code": "google-provider-code", "response": "json"},
        )
        token_response = await client.post(
            "/api/v1/auth/token",
            json={
                "code": callback_response.json()["authorization_code"],
                "code_verifier": verifier,
            },
        )

    assert start_response.status_code == 200
    assert "accounts.google.com" in authorization_url
    assert callback_response.status_code == 200
    assert callback_response.json()["redirect_url"] == "https://app.example.com/auth/callback"
    assert "authorization_code" in callback_response.json()
    assert token_response.status_code == 200
    assert token_response.json()["user"]["name"] == "Google User"
