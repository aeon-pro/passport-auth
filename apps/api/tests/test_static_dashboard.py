import pytest
from httpx import ASGITransport, AsyncClient

from passport_auth.main import create_app


@pytest.mark.asyncio
async def test_serves_dashboard_assets_and_routes(tmp_path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><h1>Dashboard</h1>", encoding="utf-8")
    (tmp_path / "styles.css").write_text("body { color: white; }", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('plain dashboard');", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('dashboard');", encoding="utf-8")
    transport = ASGITransport(app=create_app(static_dir=tmp_path))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        root_response = await client.get("/")
        setup_response = await client.get("/setup")
        stylesheet_response = await client.get("/styles.css")
        script_response = await client.get("/app.js")
        asset_response = await client.get("/assets/app.js")
        api_response = await client.get("/api/v1/missing")

    assert root_response.status_code == 200
    assert "<h1>Dashboard</h1>" in root_response.text
    assert setup_response.status_code == 200
    assert "<h1>Dashboard</h1>" in setup_response.text
    assert stylesheet_response.status_code == 200
    assert stylesheet_response.text == "body { color: white; }"
    assert script_response.status_code == 200
    assert script_response.text == "console.log('plain dashboard');"
    assert asset_response.status_code == 200
    assert asset_response.text == "console.log('dashboard');"
    assert api_response.status_code == 404
