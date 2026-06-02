from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from passport_auth.api.v1.dashboard_auth import get_current_dashboard_user, get_setup_store
from passport_auth.setup.store import DashboardSettings, OwnerAccount, SetupStore

router = APIRouter(prefix="/dashboard/settings", tags=["dashboard-settings"])


class DashboardSettingsResponse(BaseModel):
    app_domain: str
    auth_domain: str
    allowed_origins: list[str]
    redirect_urls: list[str]
    resend_from_email: str
    resend_configured: bool
    google_client_id: str
    google_configured: bool
    brand_name: str
    primary_color: str
    password_login_enabled: bool
    otp_login_enabled: bool
    magic_link_enabled: bool
    google_oauth_enabled: bool
    password_reset_otp_enabled: bool


class DashboardSettingsUpdate(BaseModel):
    app_domain: str | None = Field(default=None, max_length=255)
    auth_domain: str | None = Field(default=None, max_length=255)
    allowed_origins: list[str] | None = None
    redirect_urls: list[str] | None = None
    resend_from_email: str | None = Field(default=None, max_length=320)
    resend_api_key: str | None = Field(default=None, max_length=2048)
    google_client_id: str | None = Field(default=None, max_length=1024)
    google_client_secret: str | None = Field(default=None, max_length=2048)
    brand_name: str | None = Field(default=None, max_length=80)
    primary_color: str | None = Field(default=None, max_length=32)
    password_login_enabled: bool | None = None
    otp_login_enabled: bool | None = None
    magic_link_enabled: bool | None = None
    google_oauth_enabled: bool | None = None
    password_reset_otp_enabled: bool | None = None

    @field_validator(
        "app_domain",
        "auth_domain",
        "resend_from_email",
        "resend_api_key",
        "google_client_id",
        "google_client_secret",
        "brand_name",
        "primary_color",
    )
    @classmethod
    def strip_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip()

    @field_validator("allowed_origins", "redirect_urls")
    @classmethod
    def clean_url_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None

        return [item.strip() for item in value if item.strip()]


def build_settings_response(settings: DashboardSettings) -> DashboardSettingsResponse:
    return DashboardSettingsResponse(
        app_domain=settings.app_domain,
        auth_domain=settings.auth_domain,
        allowed_origins=list(settings.allowed_origins),
        redirect_urls=list(settings.redirect_urls),
        resend_from_email=settings.resend_from_email,
        resend_configured=bool(settings.resend_api_key),
        google_client_id=settings.google_client_id,
        google_configured=bool(settings.google_client_secret),
        brand_name=settings.brand_name,
        primary_color=settings.primary_color,
        password_login_enabled=settings.password_login_enabled,
        otp_login_enabled=settings.otp_login_enabled,
        magic_link_enabled=settings.magic_link_enabled,
        google_oauth_enabled=settings.google_oauth_enabled,
        password_reset_otp_enabled=settings.password_reset_otp_enabled,
    )


@router.get("")
def get_dashboard_settings(
    _owner: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
) -> DashboardSettingsResponse:
    return build_settings_response(setup_store.get_dashboard_settings())


@router.put("")
def update_dashboard_settings(
    payload: DashboardSettingsUpdate,
    _owner: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
) -> DashboardSettingsResponse:
    current = setup_store.get_dashboard_settings()
    updates = payload.model_dump(exclude_unset=True)

    if "allowed_origins" in updates:
        updates["allowed_origins"] = tuple(updates["allowed_origins"])
    if "redirect_urls" in updates:
        updates["redirect_urls"] = tuple(updates["redirect_urls"])
    if updates.get("resend_api_key") == "":
        updates.pop("resend_api_key")
    if updates.get("google_client_secret") == "":
        updates.pop("google_client_secret")

    updated_settings = replace(current, **updates)
    saved_settings = setup_store.save_dashboard_settings(updated_settings)
    return build_settings_response(saved_settings)
