import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.main import create_app
from passport_auth.setup.store import InMemorySetupStore


@pytest.mark.asyncio
async def test_setup_status_is_open_before_owner_exists() -> None:
    transport = ASGITransport(app=create_app(setup_store=InMemorySetupStore()))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/setup/status")

    assert response.status_code == 200
    assert response.json() == {"setup_complete": False, "owner": None}


@pytest.mark.asyncio
async def test_owner_setup_creates_owner_and_hashes_password() -> None:
    setup_store = InMemorySetupStore()
    transport = ASGITransport(app=create_app(setup_store=setup_store))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/setup/owner",
            json={"email": "Owner@Example.com", "password": "correct-horse-battery-staple"},
        )
        status_response = await client.get("/api/v1/setup/status")

    assert response.status_code == 201
    assert response.json() == {
        "setup_complete": True,
        "owner": {"email": "owner@example.com"},
    }
    assert status_response.json() == {
        "setup_complete": True,
        "owner": {"email": "owner@example.com"},
    }
    assert setup_store.owner is not None
    assert setup_store.owner.password_hash.startswith("pbkdf2_sha256$")
    assert "correct-horse-battery-staple" not in setup_store.owner.password_hash


@pytest.mark.asyncio
async def test_owner_setup_locks_after_first_owner() -> None:
    transport = ASGITransport(app=create_app(setup_store=InMemorySetupStore()))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first_response = await client.post(
            "/api/v1/setup/owner",
            json={"email": "owner@example.com", "password": "correct-horse-battery-staple"},
        )
        second_response = await client.post(
            "/api/v1/setup/owner",
            json={"email": "second@example.com", "password": "correct-horse-battery-staple"},
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Setup is already complete."}


@pytest.mark.asyncio
async def test_owner_setup_rejects_short_password() -> None:
    transport = ASGITransport(app=create_app(setup_store=InMemorySetupStore()))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/setup/owner",
            json={"email": "owner@example.com", "password": "short"},
        )

    assert response.status_code == 422
