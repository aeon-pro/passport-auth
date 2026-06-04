from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_encryption_key: str = "local-development-secret-change-me"
    database_url: str | None = None
    dashboard_jwt_ttl_seconds: int = 31_536_000
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
