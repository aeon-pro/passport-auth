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
    assert "${POSTGRES_PASSWORD:-}@postgres:5432/" in compose
    assert "REDIS_URL=${REDIS_URL:-redis://redis:6379/0}" in compose
    assert "CLICKHOUSE_URL=${CLICKHOUSE_URL:-http://" in compose
    assert "${CLICKHOUSE_PASSWORD:-}@clickhouse:8123/" in compose
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
    assert "APP_ENCRYPTION_KEY=${APP_ENCRYPTION_KEY:-}" in compose
    assert "DASHBOARD_JWT_SECRET=${DASHBOARD_JWT_SECRET:-}" in compose
    assert "PUBLIC_JWT_SECRET=${PUBLIC_JWT_SECRET:-}" in compose
    assert "DASHBOARD_JWT_TTL_SECONDS=${DASHBOARD_JWT_TTL_SECONDS:-28800}" in compose
    assert "must be set" not in compose
    assert "DASHBOARD_JWT_SECRET=replace-with-a-different-32-byte-minimum-secret" in env_example
    assert "PUBLIC_JWT_SECRET=replace-with-another-32-byte-minimum-secret" in env_example
    assert "DASHBOARD_JWT_TTL_SECONDS=28800" in env_example
    assert "POSTGRES_PASSWORD=replace-with-a-strong-postgres-password" in env_example
    assert "CLICKHOUSE_PASSWORD=replace-with-a-strong-clickhouse-password" in env_example
    assert "DATABASE_URL=" not in env_example
    assert "CLICKHOUSE_URL=" not in env_example


def test_dashboard_app_uses_session_storage_for_dashboard_tokens() -> None:
    app_js = (ROOT / "apps" / "web" / "app.js").read_text(encoding="utf-8")

    assert 'resolveBrowserStorage("sessionStorage")' in app_js
    assert 'resolveBrowserStorage("localStorage")?.removeItem(TOKEN_KEY)' in app_js
    assert "localStorage.setItem(TOKEN_KEY" not in app_js
    assert "window.localStorage.setItem(TOKEN_KEY" not in app_js
