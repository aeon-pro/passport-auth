import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.main import create_app


@pytest.mark.asyncio
async def test_health_endpoint_reports_service_status() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "passport-auth-api"}
