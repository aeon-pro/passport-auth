import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.core.config import Settings
from passport_auth.main import create_app
from passport_auth.setup.store import InMemorySetupStore


async def login_owner(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/dashboard/auth/login",
        json={
            "email": "owner@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    return str(response.json()["access_token"])


class FakeAnalyticsReader:
    def summary(self):
        return {
            "enabled": True,
            "reason": "",
            "overview": {
                "dau": 12,
                "wau": 28,
                "mau": 63,
                "signups": 9,
                "logins": 41,
                "login_success_rate": 97.6,
                "failures": 1,
                "refreshes": 22,
                "active_users": 37,
            },
            "retention": [
                {"label": "Week 1", "value": 82.0},
                {"label": "Week 2", "value": 64.5},
                {"label": "Week 3", "value": 51.0},
                {"label": "Week 4", "value": 42.0},
            ],
            "methods": [
                {"method": "password", "count": 25},
                {"method": "google", "count": 16},
            ],
            "recent_events": [
                {
                    "event_type": "login_success",
                    "auth_method": "google",
                    "status": "success",
                    "email": "ada@example.com",
                    "occurred_at": "2026-06-18T08:00:00Z",
                    "reason": "",
                }
            ],
        }


def create_dashboard_app(*, settings: Settings, analytics_reader=None):
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    return create_app(
        settings=settings,
        setup_store=setup_store,
        analytics_reader=analytics_reader,
    )


@pytest.mark.asyncio
async def test_dashboard_analytics_requires_dashboard_authentication() -> None:
    app = create_dashboard_app(
        settings=Settings(app_encryption_key="test-dashboard-analytics-secret")
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/dashboard/analytics/summary")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_analytics_reports_disabled_outside_production() -> None:
    app = create_dashboard_app(
        settings=Settings(
            app_env="development",
            app_encryption_key="test-dashboard-analytics-secret",
            clickhouse_url="http://clickhouse:8123/passport_auth",
        )
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        response = await client.get(
            "/api/v1/dashboard/analytics/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["reason"] == "Analytics are only recorded in production with ClickHouse enabled."
    assert body["overview"]["dau"] == 0
    assert body["retention"] == [
        {"label": "Week 1", "value": 0.0},
        {"label": "Week 2", "value": 0.0},
        {"label": "Week 3", "value": 0.0},
        {"label": "Week 4", "value": 0.0},
    ]


@pytest.mark.asyncio
async def test_dashboard_analytics_returns_reader_summary_in_production() -> None:
    app = create_dashboard_app(
        settings=Settings(
            app_env="production",
            app_encryption_key="test-dashboard-analytics-secret",
            clickhouse_url="http://clickhouse:8123/passport_auth",
        ),
        analytics_reader=FakeAnalyticsReader(),
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        response = await client.get(
            "/api/v1/dashboard/analytics/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["overview"]["dau"] == 12
    assert body["overview"]["login_success_rate"] == 97.6
    assert body["methods"] == [
        {"method": "password", "count": 25},
        {"method": "google", "count": 16},
    ]
    assert body["recent_events"][0]["email"] == "ada@example.com"
