import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_compose_persists_dashboard_uploaded_assets() -> None:
    compose = (ROOT / "docker-compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "docker-entrypoint.sh").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "APP_ENV=${APP_ENV:-production}" in compose
    assert "APP_ENV=development" in env_example
    assert "profiles:" not in compose
    assert "secrets-init:" in compose
    assert "runtime-secrets:/run/passport-auth-secrets" in compose
    assert "condition: service_completed_successfully" in compose
    assert "DATABASE_URL=" not in compose
    assert "DATABASE_URL=" in entrypoint
    assert "SERVICE_PASSWORD_64_POSTGRES" in entrypoint
    assert "REDIS_URL=${REDIS_URL:-redis://redis:6379/0}" in compose
    assert "CLICKHOUSE_URL=" not in compose
    assert "CLICKHOUSE_URL=" in entrypoint
    assert "SERVICE_PASSWORD_64_CLICKHOUSE" in entrypoint
    assert "postgres:\n        condition: service_healthy" in compose
    assert "redis:\n        condition: service_healthy" in compose
    assert "clickhouse:\n        condition: service_healthy" in compose
    assert 'ports:\n      - "8000:8000"' not in compose
    assert "expose:\n      - \"8000\"" in compose
    assert "DASHBOARD_ASSET_DIR=${DASHBOARD_ASSET_DIR:-/app/data/dashboard-assets}" in compose
    assert "dashboard-assets:/app/data/dashboard-assets" in compose
    assert "name: passport-auth_postgres-data" in compose
    assert "name: passport-auth_redis-data" in compose
    assert "name: passport-auth_clickhouse-data" in compose
    assert "name: passport-auth_dashboard-assets" in compose
    assert "name: passport-auth_runtime-secrets" in compose
    assert "DASHBOARD_ASSET_DIR=/app/data/dashboard-assets" in env_example
    assert "DASHBOARD_ASSET_DIR=/app/data/dashboard-assets" in dockerfile
    assert "ENTRYPOINT [\"passport-auth-entrypoint\"]" in dockerfile
    assert "- APP_ENCRYPTION_KEY=" not in compose
    assert "- DASHBOARD_JWT_SECRET=" not in compose
    assert "- PUBLIC_JWT_SECRET=" not in compose
    assert (
        "SERVICE_BASE64_64_APP_ENCRYPTION_KEY=${SERVICE_BASE64_64_APP_ENCRYPTION_KEY:-}"
        in compose
    )
    assert "SERVICE_BASE64_64_DASHBOARD_JWT_SECRET" in compose
    assert "SERVICE_BASE64_64_PUBLIC_JWT_SECRET" in compose
    assert "DASHBOARD_JWT_TTL_SECONDS=${DASHBOARD_JWT_TTL_SECONDS:-28800}" in compose
    assert "must be set" not in compose
    assert "POSTGRES_PASSWORD:" not in compose
    assert "POSTGRES_PASSWORD_FILE: /run/passport-auth-secrets/postgres_password" in compose
    assert "CLICKHOUSE_PASSWORD:" not in compose
    assert "`cat /run/passport-auth-secrets/clickhouse_password`" in compose
    assert "export CLICKHOUSE_USER=passport" in compose
    assert "python - <<'PY'" in compose
    assert "configs:" not in compose
    assert "python3 scripts/generate-env.py" in readme
    assert "SERVICE_BASE64_64_DASHBOARD_JWT_SECRET=" in env_example
    assert "SERVICE_BASE64_64_PUBLIC_JWT_SECRET=" in env_example
    assert "DASHBOARD_JWT_TTL_SECONDS=28800" in env_example
    assert "SERVICE_PASSWORD_64_POSTGRES=" in env_example
    assert "SERVICE_PASSWORD_64_CLICKHOUSE=" in env_example
    assert "POSTGRES_PASSWORD=" not in env_example
    assert "CLICKHOUSE_PASSWORD=" not in env_example
    assert "DATABASE_URL=" not in env_example
    assert "CLICKHOUSE_URL=" not in env_example


def test_generate_env_script_writes_secure_random_values(tmp_path) -> None:
    output = tmp_path / ".env"

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate-env.py"), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )

    values = dict(
        line.split("=", 1)
        for line in output.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    generated_keys = [
        "SERVICE_BASE64_64_APP_ENCRYPTION_KEY",
        "SERVICE_BASE64_64_DASHBOARD_JWT_SECRET",
        "SERVICE_BASE64_64_PUBLIC_JWT_SECRET",
        "SERVICE_PASSWORD_64_POSTGRES",
        "SERVICE_PASSWORD_64_CLICKHOUSE",
    ]

    assert output.stat().st_mode & 0o077 == 0
    assert len({values[key] for key in generated_keys}) == len(generated_keys)
    for key in generated_keys:
        assert len(values[key]) == 64
        assert values[key].isalnum()


def test_runtime_secret_generator_writes_stable_secret_files(tmp_path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate-runtime-secrets.py"),
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    original_values = {
        path.name: path.read_text(encoding="utf-8").strip()
        for path in tmp_path.iterdir()
    }

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate-runtime-secrets.py"),
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    next_values = {
        path.name: path.read_text(encoding="utf-8").strip()
        for path in tmp_path.iterdir()
    }

    assert set(original_values) == {
        "app_encryption_key",
        "dashboard_jwt_secret",
        "public_jwt_secret",
        "postgres_password",
        "clickhouse_password",
    }
    assert next_values == original_values
    assert len(set(original_values.values())) == len(original_values)
    for value in original_values.values():
        assert len(value) == 64
        assert value.isalnum()


def test_dashboard_app_uses_session_storage_for_dashboard_tokens() -> None:
    app_js = (ROOT / "apps" / "web" / "app.js").read_text(encoding="utf-8")

    assert 'resolveBrowserStorage("sessionStorage")' in app_js
    assert 'resolveBrowserStorage("localStorage")?.removeItem(TOKEN_KEY)' in app_js
    assert "localStorage.setItem(TOKEN_KEY" not in app_js
    assert "window.localStorage.setItem(TOKEN_KEY" not in app_js
