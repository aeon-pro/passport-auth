#!/bin/sh
set -eu

export APP_ENV="${APP_ENV:-production}"
export WEB_STATIC_DIR="${WEB_STATIC_DIR:-/app/static}"
export DASHBOARD_ASSET_DIR="${DASHBOARD_ASSET_DIR:-/app/data/dashboard-assets}"
export DASHBOARD_JWT_TTL_SECONDS="${DASHBOARD_JWT_TTL_SECONDS:-28800}"
export REDIS_URL="${REDIS_URL:-redis://redis:6379/0}"
secret_dir="${PASSPORT_AUTH_SECRET_DIR:-/run/passport-auth-secrets}"

read_secret_file() {
  if [ -s "$1" ]; then
    tr -d '\r\n' < "$1"
  fi
}

read_private_key_file() {
  if [ -s "$1" ]; then
    cat "$1"
  fi
}

value_from_file_or_env() {
  explicit_value="$(eval "printf '%s' \"\${$1:-}\"")"
  generated_value="$(read_secret_file "$2")"
  fallback_value="$(eval "printf '%s' \"\${$3:-}\"")"
  if [ -n "$explicit_value" ]; then
    printf '%s' "$explicit_value"
  elif [ -n "$generated_value" ]; then
    printf '%s' "$generated_value"
  else
    printf '%s' "$fallback_value"
	  fi
}

public_jwt_private_key() {
  explicit_value="${PUBLIC_JWT_PRIVATE_KEY:-}"
  generated_value="$(read_private_key_file "$secret_dir/public_jwt_private_key")"
  fallback_value="${PUBLIC_JWT_PRIVATE_KEY_B64:-}"
  if [ -n "$explicit_value" ]; then
    printf '%s' "$explicit_value"
  elif [ -n "$generated_value" ]; then
    printf '%s' "$generated_value"
  elif [ -n "$fallback_value" ]; then
    python - "$fallback_value" <<'PY'
import base64
import sys

sys.stdout.write(base64.b64decode(sys.argv[1]).decode("utf-8"))
PY
  else
    python - "$secret_dir/public_jwt_private_key" <<'PY'
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
private_key_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("ascii")
path.write_text(private_key_pem, encoding="utf-8")
path.chmod(0o444)
sys.stdout.write(private_key_pem)
PY
  fi
}

export APP_ENCRYPTION_KEY="$(value_from_file_or_env APP_ENCRYPTION_KEY "$secret_dir/app_encryption_key" SERVICE_BASE64_64_APP_ENCRYPTION_KEY)"
export DASHBOARD_JWT_SECRET="$(value_from_file_or_env DASHBOARD_JWT_SECRET "$secret_dir/dashboard_jwt_secret" SERVICE_BASE64_64_DASHBOARD_JWT_SECRET)"
export PUBLIC_JWT_PRIVATE_KEY="$(public_jwt_private_key)"

postgres_password="$(value_from_file_or_env PASSPORT_AUTH_POSTGRES_PASSWORD "$secret_dir/postgres_password" SERVICE_PASSWORD_64_POSTGRES)"
clickhouse_password="$(value_from_file_or_env PASSPORT_AUTH_CLICKHOUSE_PASSWORD "$secret_dir/clickhouse_password" SERVICE_PASSWORD_64_CLICKHOUSE)"

export DATABASE_URL="${DATABASE_URL:-postgresql://passport:${postgres_password}@postgres:5432/passport_auth}"
export CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://passport:${clickhouse_password}@clickhouse:8123/passport_auth}"

exec "$@"
