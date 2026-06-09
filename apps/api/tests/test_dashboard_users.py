import base64
import hashlib

import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.auth.store import InMemoryAuthStore
from passport_auth.core.config import Settings
from passport_auth.main import create_app
from passport_auth.setup.store import DashboardSettings, InMemorySetupStore


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


async def login_owner(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/dashboard/auth/login",
        json={
            "email": "owner@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    return str(response.json()["access_token"])


def create_users_app() -> tuple[InMemoryAuthStore, object]:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    setup_store.save_dashboard_settings(
        DashboardSettings(redirect_urls=("https://app.example.com/auth/callback",))
    )
    auth_store = InMemoryAuthStore()
    app = create_app(
        settings=Settings(app_encryption_key="test-users-secret"),
        setup_store=setup_store,
        auth_store=auth_store,
    )
    return auth_store, app


@pytest.mark.asyncio
async def test_dashboard_users_require_owner_token() -> None:
    _, app = create_users_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/dashboard/users")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_users_list_search_and_update_metadata() -> None:
    auth_store, app = create_users_app()
    ada = auth_store.create_user(
        email="ada@example.com",
        name="Ada Lovelace",
        password="correct-horse-battery-staple",
        user_metadata={
            "plan": "starter",
            "subscription": {"status": "trialing"},
        },
    )
    auth_store.create_user(
        email="grace@example.com",
        name="Grace Hopper",
        password="correct-horse-battery-staple",
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        headers = {"Authorization": f"Bearer {token}"}
        list_response = await client.get("/api/v1/dashboard/users", headers=headers)
        search_response = await client.get(
            "/api/v1/dashboard/users",
            headers=headers,
            params={"query": "ada"},
        )
        update_response = await client.patch(
            f"/api/v1/dashboard/users/{ada.id}",
            headers=headers,
            json={
                "name": "Ada Byron",
                "email_verified": False,
                "user_metadata": {
                    "plan": "pro",
                    "subscription": {"status": "active", "stripe_id": "sub_123"},
                },
            },
        )

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 2
    assert {user["email"] for user in list_response.json()["users"]} == {
        "ada@example.com",
        "grace@example.com",
    }
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 1
    assert search_response.json()["users"][0]["email"] == "ada@example.com"
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Ada Byron"
    assert update_response.json()["email_verified"] is False
    assert update_response.json()["user_metadata"] == {
        "plan": "pro",
        "subscription": {"status": "active", "stripe_id": "sub_123"},
    }


@pytest.mark.asyncio
async def test_dashboard_users_show_auth_activity_after_login() -> None:
    auth_store, app = create_users_app()
    user = auth_store.create_user(
        email="activity@example.com",
        name="Activity User",
        password="correct-horse-battery-staple",
    )
    verifier = "correct horse battery staple public verifier"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        login_response = await client.post(
            "/api/v1/auth/password/login",
            json={
                "email": "activity@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )
        detail_response = await client.get(
            "/api/v1/dashboard/users",
            headers={"Authorization": f"Bearer {token}"},
            params={"query": "activity@example.com"},
        )

    assert login_response.status_code == 200
    assert detail_response.status_code == 200
    dashboard_user = detail_response.json()["users"][0]
    assert dashboard_user["id"] == user.id
    assert dashboard_user["created_at"]
    assert dashboard_user["first_auth_method"] == "password"
    assert dashboard_user["last_auth_method"] == "password"
    assert dashboard_user["last_login_at"]
    assert dashboard_user["login_count"] == 1


@pytest.mark.asyncio
async def test_dashboard_users_deactivate_blocks_password_login() -> None:
    auth_store, app = create_users_app()
    user = auth_store.create_user(
        email="inactive@example.com",
        name="Inactive User",
        password="correct-horse-battery-staple",
    )
    verifier = "correct horse battery staple public verifier"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        deactivate_response = await client.patch(
            f"/api/v1/dashboard/users/{user.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )
        login_response = await client.post(
            "/api/v1/auth/password/login",
            json={
                "email": "inactive@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )

    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False
    assert login_response.status_code == 403
    assert login_response.json() == {"detail": "User is deactivated."}


@pytest.mark.asyncio
async def test_dashboard_users_block_with_support_message_blocks_password_login() -> None:
    auth_store, app = create_users_app()
    user = auth_store.create_user(
        email="blocked@example.com",
        name="Blocked User",
        password="correct-horse-battery-staple",
    )
    verifier = "correct horse battery staple public verifier"
    block_message = "Your account is blocked. Contact support for billing review."
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        block_response = await client.patch(
            f"/api/v1/dashboard/users/{user.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_blocked": True, "blocked_message": block_message},
        )
        login_response = await client.post(
            "/api/v1/auth/password/login",
            json={
                "email": "blocked@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )

    assert block_response.status_code == 200
    assert block_response.json()["is_blocked"] is True
    assert block_response.json()["blocked_message"] == block_message
    assert login_response.status_code == 403
    assert login_response.json() == {"detail": block_message}


@pytest.mark.asyncio
async def test_public_me_returns_custom_user_metadata() -> None:
    auth_store, app = create_users_app()
    auth_store.create_user(
        email="metadata@example.com",
        name="Metadata User",
        password="correct-horse-battery-staple",
        user_metadata={"plan": "enterprise", "seats": 12},
    )
    verifier = "correct horse battery staple public verifier"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login_response = await client.post(
            "/api/v1/auth/password/login",
            json={
                "email": "metadata@example.com",
                "password": "correct-horse-battery-staple",
                "redirect_url": "https://app.example.com/auth/callback",
                "code_challenge": pkce_challenge(verifier),
            },
        )
        token_response = await client.post(
            "/api/v1/auth/token",
            json={
                "code": login_response.json()["authorization_code"],
                "code_verifier": verifier,
            },
        )
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
        )

    assert token_response.status_code == 200
    assert token_response.json()["user"]["user_metadata"] == {
        "plan": "enterprise",
        "seats": 12,
    }
    assert me_response.status_code == 200
    assert me_response.json()["user_metadata"] == {
        "plan": "enterprise",
        "seats": 12,
    }
