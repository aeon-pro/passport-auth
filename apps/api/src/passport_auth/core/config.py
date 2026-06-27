import base64
from functools import cached_property, lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from passport_auth.auth.tokens import (
    generate_public_token_private_key_pem,
    public_jwks,
    public_key_id,
    public_key_pem,
)

KNOWN_INSECURE_SECRETS = {
    "",
    "local-development-secret-change-me",
    "passport-auth-change-this-stable-secret",
    "replace-with-a-32-byte-minimum-secret",
    "replace-with-a-different-32-byte-minimum-secret",
    "replace-with-another-32-byte-minimum-secret",
}
MIN_PRODUCTION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    app_env: str = "development"
    app_encryption_key: str = "local-development-secret-change-me"
    clickhouse_url: str | None = None
    database_url: str | None = None
    redis_url: str | None = None
    dashboard_jwt_secret: str | None = None
    public_jwt_private_key: str | None = None
    public_jwt_private_key_b64: str | None = None
    public_jwt_issuer: str = "passport-auth"
    public_jwt_audience: str = "passport-auth-app"
    dashboard_jwt_ttl_seconds: int = 28_800
    public_access_token_ttl_seconds: int = 900
    public_refresh_token_ttl_seconds: int = 31_536_000
    public_auth_code_ttl_seconds: int = 300
    public_otp_ttl_seconds: int = 600
    public_magic_link_ttl_seconds: int = 900
    public_oauth_state_ttl_seconds: int = 600
    password_reset_otp_enabled: bool = True
    password_reset_otp_ttl_seconds: int = 600
    dashboard_asset_dir: Path = Path("/tmp/passport-auth/dashboard-assets")
    web_static_dir: Path | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def resolved_dashboard_jwt_secret(self) -> str:
        return self.dashboard_jwt_secret or self.app_encryption_key

    @cached_property
    def resolved_public_jwt_private_key(self) -> str:
        if self.public_jwt_private_key:
            return normalize_private_key_pem(self.public_jwt_private_key)
        if self.public_jwt_private_key_b64:
            return base64.b64decode(self.public_jwt_private_key_b64).decode("utf-8")
        return generate_public_token_private_key_pem()

    @property
    def public_jwt_public_key_pem(self) -> str:
        return public_key_pem(self.resolved_public_jwt_private_key)

    @property
    def public_jwt_key_id(self) -> str:
        return public_key_id(self.resolved_public_jwt_private_key)

    @property
    def public_jwt_jwks(self) -> dict[str, list[dict[str, str]]]:
        return public_jwks(self.resolved_public_jwt_private_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_security(settings: Settings) -> None:
    if settings.app_env.strip().lower() != "production":
        return

    _require_production_secret("APP_ENCRYPTION_KEY", settings.app_encryption_key)
    _require_production_secret("DASHBOARD_JWT_SECRET", settings.dashboard_jwt_secret)
    if not (settings.public_jwt_private_key or settings.public_jwt_private_key_b64 or "").strip():
        raise RuntimeError(
            "PUBLIC_JWT_PRIVATE_KEY or PUBLIC_JWT_PRIVATE_KEY_B64 must be set in production."
        )

    if settings.dashboard_jwt_secret == settings.app_encryption_key:
        raise RuntimeError("DASHBOARD_JWT_SECRET must be different from APP_ENCRYPTION_KEY.")
    public_key_id(settings.resolved_public_jwt_private_key)


def _require_production_secret(name: str, value: str | None) -> None:
    cleaned = (value or "").strip()
    if cleaned in KNOWN_INSECURE_SECRETS or len(cleaned) < MIN_PRODUCTION_SECRET_LENGTH:
        raise RuntimeError(
            f"{name} must be set to a unique secret of at least "
            f"{MIN_PRODUCTION_SECRET_LENGTH} characters in production."
        )


def normalize_private_key_pem(value: str) -> str:
    return value.replace("\\n", "\n")
