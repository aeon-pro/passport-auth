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


def create_test_app(asset_dir) -> object:
    setup_store = InMemorySetupStore()
    setup_store.create_owner(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    return create_app(
        settings=Settings(
            app_encryption_key="test-jwt-secret",
            dashboard_asset_dir=asset_dir,
        ),
        setup_store=setup_store,
    )


@pytest.mark.asyncio
async def test_dashboard_logo_upload_requires_owner_token(tmp_path) -> None:
    transport = ASGITransport(app=create_test_app(tmp_path / "dashboard-assets"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/dashboard/assets/logos/primary",
            files={"file": ("logo.png", b"\x89PNG\r\n\x1a\nlogo", "image/png")},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_logo_upload_persists_and_serves_asset(tmp_path) -> None:
    asset_dir = tmp_path / "dashboard-assets"
    transport = ASGITransport(app=create_test_app(asset_dir))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        response = await client.post(
            "/api/v1/dashboard/assets/logos/primary",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("Acme Logo.PNG", b"\x89PNG\r\n\x1a\nlogo", "image/png")},
        )
        body = response.json()
        asset_response = await client.get(body["url"])

    assert response.status_code == 201
    assert body["slot"] == "primary"
    assert body["url"].startswith("/dashboard-assets/logos/primary-")
    assert body["url"].endswith(".png")
    assert (asset_dir / body["url"].removeprefix("/dashboard-assets/")).read_bytes() == (
        b"\x89PNG\r\n\x1a\nlogo"
    )
    assert asset_response.status_code == 200
    assert asset_response.content == b"\x89PNG\r\n\x1a\nlogo"


@pytest.mark.asyncio
async def test_dashboard_logo_upload_rejects_non_image_files(tmp_path) -> None:
    transport = ASGITransport(app=create_test_app(tmp_path / "dashboard-assets"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        response = await client.post(
            "/api/v1/dashboard/assets/logos/mark",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("notes.txt", b"not an image", "text/plain")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Logo must be a PNG, JPG, or WebP image."


@pytest.mark.asyncio
async def test_dashboard_logo_upload_rejects_svg_files(tmp_path) -> None:
    transport = ASGITransport(app=create_test_app(tmp_path / "dashboard-assets"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await login_owner(client)
        response = await client.post(
            "/api/v1/dashboard/assets/logos/primary",
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (
                    "logo.svg",
                    b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
                    "image/svg+xml",
                )
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Logo must be a PNG, JPG, or WebP image."
