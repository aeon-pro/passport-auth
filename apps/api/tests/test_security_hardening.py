import inspect

import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.analytics import disabled_analytics_summary
from passport_auth.auth.store import InMemoryAuthStore, PostgresAuthStore
from passport_auth.core.config import Settings
from passport_auth.core.rate_limit import RedisRateLimiter
from passport_auth.dashboard.tokens import create_dashboard_token
from passport_auth.main import create_app
from passport_auth.setup.store import DashboardSettings, InMemorySetupStore, PostgresSetupStore

STRONG_ENCRYPTION_KEY = "enc-test-secret-value-that-is-long-enough"
STRONG_DASHBOARD_JWT_SECRET = "dash-test-secret-value-that-is-long-enough"
STRONG_PUBLIC_JWT_SECRET = "public-test-secret-value-that-is-long-enough"


class FakeAnalyticsReader:
    def summary(self):
        summary = disabled_analytics_summary()
        summary["enabled"] = True
        return summary


async def login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/dashboard/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "app_encryption_key": STRONG_ENCRYPTION_KEY,
        "dashboard_jwt_secret": STRONG_DASHBOARD_JWT_SECRET,
        "public_jwt_secret": STRONG_PUBLIC_JWT_SECRET,
    }
    values.update(overrides)
    return Settings(**values)


def create_setup_store_with_owner() -> InMemorySetupStore:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    setup_store.save_dashboard_settings(
        DashboardSettings(
            redirect_urls=("https://app.example.com/auth/callback",),
            allowed_origins=("https://app.example.com",),
        )
    )
    return setup_store


def invite_and_accept_admin(setup_store: InMemorySetupStore) -> None:
    setup_store.create_dashboard_invite(
        email="admin@example.com",
        role="admin",
        token="admin-invite-token-with-enough-entropy",
        expires_at=4_102_444_800,
    )
    setup_store.accept_dashboard_invite(
        token="admin-invite-token-with-enough-entropy",
        password="admin-correct-horse-battery-staple",
        now=1,
    )


def test_production_rejects_known_default_runtime_secrets() -> None:
    setup_store = create_setup_store_with_owner()

    with pytest.raises(RuntimeError, match="APP_ENCRYPTION_KEY"):
        create_app(
            settings=Settings(
                app_env="production",
                app_encryption_key="passport-auth-change-this-stable-secret",
            ),
            setup_store=setup_store,
        )


@pytest.mark.asyncio
async def test_dashboard_jwt_uses_dedicated_secret_not_encryption_key() -> None:
    setup_store = create_setup_store_with_owner()
    app = create_app(settings=production_settings(), setup_store=setup_store)
    forged_with_encryption_key = create_dashboard_token(
        email="owner@example.com",
        role="owner",
        secret=STRONG_ENCRYPTION_KEY,
        ttl_seconds=300,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/dashboard/auth/me",
            headers={"Authorization": f"Bearer {forged_with_encryption_key}"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_setup_status_hides_owner_email_after_setup() -> None:
    setup_store = create_setup_store_with_owner()
    app = create_app(
        settings=Settings(app_encryption_key="test-setup-secret"),
        setup_store=setup_store,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/setup/status")

    assert response.status_code == 200
    assert response.json() == {"setup_complete": True, "owner": None}


@pytest.mark.asyncio
async def test_non_owner_dashboard_admin_cannot_mutate_owner_only_surfaces(tmp_path) -> None:
    setup_store = create_setup_store_with_owner()
    invite_and_accept_admin(setup_store)
    app = create_app(
        settings=Settings(
            app_encryption_key="test-owner-only-secret",
            dashboard_asset_dir=tmp_path / "dashboard-assets",
        ),
        setup_store=setup_store,
        auth_store=InMemoryAuthStore(),
        analytics_reader=FakeAnalyticsReader(),
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        admin_token = await login(
            client,
            "admin@example.com",
            "admin-correct-horse-battery-staple",
        )
        headers = {"Authorization": f"Bearer {admin_token}"}
        responses = [
            await client.get("/api/v1/dashboard/settings", headers=headers),
            await client.put(
                "/api/v1/dashboard/settings",
                headers=headers,
                json={"brand_name": "Compromised"},
            ),
            await client.get("/api/v1/dashboard/users", headers=headers),
            await client.post(
                "/api/v1/dashboard/assets/logos/primary",
                headers=headers,
                files={"file": ("logo.png", b"\x89PNG\r\n\x1a\nlogo", "image/png")},
            ),
            await client.get("/api/v1/dashboard/analytics/summary", headers=headers),
            await client.get("/api/v1/dashboard/admins", headers=headers),
        ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403, 403, 403]


def test_postgres_consumes_one_time_secrets_with_row_locks() -> None:
    auth_methods = [
        PostgresAuthStore.consume_pending_registration,
        PostgresAuthStore.consume_auth_code,
        PostgresAuthStore.consume_refresh_token,
        PostgresAuthStore.consume_otp,
        PostgresAuthStore.consume_magic_link,
        PostgresAuthStore.consume_oauth_state,
    ]
    setup_methods = [
        PostgresSetupStore.accept_dashboard_invite,
        PostgresSetupStore.consume_password_reset_otp,
    ]

    for method in [*auth_methods, *setup_methods]:
        assert "FOR UPDATE" in inspect.getsource(method)


def test_redis_rate_limiter_hashes_subjects_before_storage() -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.keys: list[str] = []

        def eval(self, _script, _numkeys, key, *_args) -> int:
            self.keys.append(str(key))
            return 1

    fake_redis = FakeRedis()
    limiter = RedisRateLimiter("redis://redis:6379/0", client=fake_redis)

    assert limiter.hit(
        "public-auth:password-login:203.0.113.10:user@example.com",
        limit=5,
        window_seconds=300,
    )
    assert len(fake_redis.keys) == 1
    assert fake_redis.keys[0].startswith("passport-auth:rate-limit:")
    assert "user@example.com" not in fake_redis.keys[0]
    assert "203.0.113.10" not in fake_redis.keys[0]
