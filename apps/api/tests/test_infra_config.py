from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_compose_persists_dashboard_uploaded_assets() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "APP_ENV=${APP_ENV:-production}" in compose
    assert "APP_ENV=development" in env_example
    assert "DASHBOARD_ASSET_DIR=${DASHBOARD_ASSET_DIR:-/app/data/dashboard-assets}" in compose
    assert "dashboard-assets:/app/data/dashboard-assets" in compose
    assert "dashboard-assets:" in compose
    assert "DASHBOARD_ASSET_DIR=/app/data/dashboard-assets" in env_example
    assert "DASHBOARD_ASSET_DIR=/app/data/dashboard-assets" in dockerfile
