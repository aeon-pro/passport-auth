from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.core.config import Settings
from passport_auth.main import create_app
from passport_auth.setup.store import DashboardSettings, InMemorySetupStore


class CapturingEmailSender:
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
                "settings": settings,
            }
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


def create_admins_app() -> tuple[InMemorySetupStore, CapturingEmailSender, object]:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    setup_store.save_dashboard_settings(
        DashboardSettings(
            auth_domain="auth.example.com",
            resend_from_email="Alactic <auth@mail.example.com>",
            resend_api_key="re_test_key",
            brand_name="Alactic",
        )
    )
    email_sender = CapturingEmailSender()
    app = create_app(
        settings=Settings(app_env="production", app_encryption_key="test-admin-secret"),
        setup_store=setup_store,
        auth_email_sender=email_sender,
    )
    return setup_store, email_sender, app


@pytest.mark.asyncio
async def test_owner_invites_dashboard_admin_and_invitee_sets_password() -> None:
    _, email_sender, app = create_admins_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        owner_token = await login_owner(client)
        headers = {"Authorization": f"Bearer {owner_token}"}
        invite_response = await client.post(
            "/api/v1/dashboard/admins/invite",
            headers=headers,
            json={"email": "admin@example.com", "role": "admin"},
        )
        list_response = await client.get("/api/v1/dashboard/admins", headers=headers)
        login_before_accept_response = await client.post(
            "/api/v1/dashboard/auth/login",
            json={
                "email": "admin@example.com",
                "password": "new-correct-horse-battery-staple",
            },
        )

        invite_link = str(email_sender.messages[0]["values"]["invite_link"])
        invite_token = parse_qs(urlparse(invite_link).query)["token"][0]
        accept_response = await client.post(
            "/api/v1/dashboard/admins/accept",
            json={
                "token": invite_token,
                "password": "new-correct-horse-battery-staple",
            },
        )
        admin_login_response = await client.post(
            "/api/v1/dashboard/auth/login",
            json={
                "email": "admin@example.com",
                "password": "new-correct-horse-battery-staple",
            },
        )
        admin_token = admin_login_response.json()["access_token"]
        me_response = await client.get(
            "/api/v1/dashboard/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert invite_response.status_code == 201
    assert invite_response.json()["user"] == {
        "email": "admin@example.com",
        "role": "admin",
        "invite_status": "pending",
    }
    assert invite_response.json()["dev_invite_url"] is None
    assert email_sender.messages[0]["template_key"] == "dashboard_invite"
    assert email_sender.messages[0]["to_email"] == "admin@example.com"
    assert invite_link.startswith("https://auth.example.com/admin-invite?token=")
    assert login_before_accept_response.status_code == 401
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 2
    assert {
        (admin["email"], admin["role"], admin["invite_status"])
        for admin in list_response.json()["admins"]
    } == {
        ("owner@example.com", "owner", "accepted"),
        ("admin@example.com", "admin", "pending"),
    }
    assert accept_response.status_code == 200
    assert accept_response.json() == {"ok": True}
    assert admin_login_response.status_code == 200
    assert admin_login_response.json()["user"] == {
        "email": "admin@example.com",
        "role": "admin",
    }
    assert me_response.status_code == 200
    assert me_response.json() == {"email": "admin@example.com", "role": "admin"}


@pytest.mark.asyncio
async def test_dashboard_admin_invites_require_owner_role() -> None:
    setup_store, _, app = create_admins_app()
    setup_store.create_dashboard_invite(
        email="admin@example.com",
        role="admin",
        token="already-invited-token",
        expires_at=4_102_444_800,
    )
    setup_store.accept_dashboard_invite(
        token="already-invited-token",
        password="new-correct-horse-battery-staple",
        now=1,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        admin_login_response = await client.post(
            "/api/v1/dashboard/auth/login",
            json={
                "email": "admin@example.com",
                "password": "new-correct-horse-battery-staple",
            },
        )
        admin_token = admin_login_response.json()["access_token"]
        invite_response = await client.post(
            "/api/v1/dashboard/admins/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "second-admin@example.com", "role": "admin"},
        )

    assert admin_login_response.status_code == 200
    assert invite_response.status_code == 403
    assert invite_response.json() == {"detail": "Only the owner can manage dashboard admins."}
