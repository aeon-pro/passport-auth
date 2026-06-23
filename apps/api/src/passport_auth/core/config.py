from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

KNOWN_INSECURE_SECRETS = {
    "",
    "local-development-secret-change-me",
    "passport-auth-change-this-stable-secret",
    "replace-with-a-32-byte-minimum-secret",
}
MIN_PRODUCTION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    app_env: str = "development"
    app_encryption_key: str = "local-development-secret-change-me"
    clickhouse_url: str | None = None
    database_url: str | None = None
    redis_url: str | None = None
    dashboard_jwt_secret: str | None = None
    public_jwt_secret: str | None = None
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

    @property
    def resolved_public_jwt_secret(self) -> str:
        return self.public_jwt_secret or self.app_encryption_key


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_security(settings: Settings) -> None:
    if settings.app_env.strip().lower() != "production":
        return

    _require_production_secret("APP_ENCRYPTION_KEY", settings.app_encryption_key)
    _require_production_secret("DASHBOARD_JWT_SECRET", settings.dashboard_jwt_secret)
    _require_production_secret("PUBLIC_JWT_SECRET", settings.public_jwt_secret)

    if settings.dashboard_jwt_secret == settings.app_encryption_key:
        raise RuntimeError("DASHBOARD_JWT_SECRET must be different from APP_ENCRYPTION_KEY.")
    if settings.public_jwt_secret == settings.app_encryption_key:
        raise RuntimeError("PUBLIC_JWT_SECRET must be different from APP_ENCRYPTION_KEY.")
    if settings.dashboard_jwt_secret == settings.public_jwt_secret:
        raise RuntimeError("DASHBOARD_JWT_SECRET must be different from PUBLIC_JWT_SECRET.")


def _require_production_secret(name: str, value: str | None) -> None:
    cleaned = (value or "").strip()
    if cleaned in KNOWN_INSECURE_SECRETS or len(cleaned) < MIN_PRODUCTION_SECRET_LENGTH:
        raise RuntimeError(
            f"{name} must be set to a unique secret of at least "
            f"{MIN_PRODUCTION_SECRET_LENGTH} characters in production."
        )
