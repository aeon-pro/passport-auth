from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_compose_persists_dashboard_uploaded_assets() -> None:
    compose = (ROOT / "docker-compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "APP_ENV=${APP_ENV:-production}" in compose
    assert "APP_ENV=development" in env_example
    assert "profiles:" not in compose
    assert "DATABASE_URL=${DATABASE_URL:-postgresql://" in compose
    assert "@postgres:5432/" in compose
    assert "REDIS_URL=${REDIS_URL:-redis://redis:6379/0}" in compose
    assert "CLICKHOUSE_URL=${CLICKHOUSE_URL:-http://" in compose
    assert "@clickhouse:8123/" in compose
    assert "postgres:\n        condition: service_healthy" in compose
    assert "redis:\n        condition: service_healthy" in compose
    assert "clickhouse:\n        condition: service_healthy" in compose
    assert 'ports:\n      - "8000:8000"' not in compose
    assert "expose:\n      - \"8000\"" in compose
    assert "DASHBOARD_ASSET_DIR=${DASHBOARD_ASSET_DIR:-/app/data/dashboard-assets}" in compose
    assert "dashboard-assets:/app/data/dashboard-assets" in compose
    assert "name: ${PASSPORT_AUTH_VOLUME_PREFIX:-passport-auth}_postgres-data" in compose
    assert "name: ${PASSPORT_AUTH_VOLUME_PREFIX:-passport-auth}_redis-data" in compose
    assert "name: ${PASSPORT_AUTH_VOLUME_PREFIX:-passport-auth}_clickhouse-data" in compose
    assert "name: ${PASSPORT_AUTH_VOLUME_PREFIX:-passport-auth}_dashboard-assets" in compose
    assert "DASHBOARD_ASSET_DIR=/app/data/dashboard-assets" in env_example
    assert "PASSPORT_AUTH_VOLUME_PREFIX=passport-auth" in env_example
    assert "DASHBOARD_ASSET_DIR=/app/data/dashboard-assets" in dockerfile
    assert "POSTGRES_PASSWORD=passport" in env_example
    assert "CLICKHOUSE_PASSWORD=passport" in env_example
    assert "DATABASE_URL=" not in env_example
    assert "CLICKHOUSE_URL=" not in env_example
