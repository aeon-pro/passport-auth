import secrets
import time
import urllib.parse
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from passport_auth.api.v1.dashboard_auth import (
    get_current_dashboard_user,
    get_settings,
    get_setup_store,
)
from passport_auth.auth.email import AuthEmailSender, EmailDeliveryError
from passport_auth.core.config import Settings
from passport_auth.setup.store import (
    DashboardSettings,
    DashboardUserAlreadyExistsError,
    OwnerAccount,
    SetupStore,
)

router = APIRouter(prefix="/dashboard/admins", tags=["dashboard-admins"])

ALLOWED_DASHBOARD_ROLES = {"admin"}
INVITE_TTL_SECONDS = 86_400
OWNER_ONLY_MESSAGE = "Only the owner can manage dashboard admins."


class DashboardAdminResponse(BaseModel):
    email: str
    role: str
    invite_status: str


class DashboardAdminsResponse(BaseModel):
    admins: list[DashboardAdminResponse]
    total: int


class InviteDashboardAdminRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(default="admin", max_length=32)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid email.")
        return normalized

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_DASHBOARD_ROLES:
            raise ValueError("Dashboard invite role must be admin.")
        return normalized


class InviteDashboardAdminResponse(BaseModel):
    sent: bool
    user: DashboardAdminResponse
    dev_invite_url: str | None = None


class AcceptDashboardInviteRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("token")
    @classmethod
    def strip_token(cls, value: str) -> str:
        return value.strip()


class OkResponse(BaseModel):
    ok: bool


def get_auth_email_sender(request: Request) -> AuthEmailSender:
    return request.app.state.auth_email_sender


def build_admin_response(user: OwnerAccount) -> DashboardAdminResponse:
    return DashboardAdminResponse(
        email=user.email,
        role=user.role,
        invite_status=user.invite_status,
    )


def require_owner(user: OwnerAccount) -> None:
    if user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=OWNER_ONLY_MESSAGE)


def dashboard_origin(dashboard_settings: DashboardSettings) -> str:
    domain = (dashboard_settings.auth_domain or dashboard_settings.app_domain).strip().rstrip("/")
    if not domain:
        return ""
    if domain.startswith(("http://", "https://")):
        return domain
    return f"https://{domain}"


def invite_link(token: str, dashboard_settings: DashboardSettings) -> str:
    path = f"/admin-invite?token={urllib.parse.quote(token)}"
    origin = dashboard_origin(dashboard_settings)
    return f"{origin}{path}" if origin else path


def send_invite_email(
    *,
    email_sender: AuthEmailSender,
    settings: Settings,
    dashboard_settings: DashboardSettings,
    to_email: str,
    link: str,
) -> None:
    if settings.app_env != "production" and not dashboard_settings.resend_api_key:
        return

    try:
        email_sender.send_template(
            template_key="dashboard_invite",
            to_email=to_email,
            values={"invite_link": link},
            settings=dashboard_settings,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("")
def list_dashboard_admins(
    _user: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
) -> DashboardAdminsResponse:
    admins = setup_store.list_dashboard_users()
    return DashboardAdminsResponse(
        admins=[build_admin_response(admin) for admin in admins],
        total=len(admins),
    )


@router.post("/invite", status_code=status.HTTP_201_CREATED)
def invite_dashboard_admin(
    payload: InviteDashboardAdminRequest,
    current_user: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    email_sender: Annotated[AuthEmailSender, Depends(get_auth_email_sender)],
) -> InviteDashboardAdminResponse:
    require_owner(current_user)
    dashboard_settings = setup_store.get_dashboard_settings()
    token = secrets.token_urlsafe(48)

    try:
        user = setup_store.create_dashboard_invite(
            email=payload.email,
            role=payload.role,
            token=token,
            expires_at=int(time.time()) + INVITE_TTL_SECONDS,
        )
    except DashboardUserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A dashboard user with this email already exists.",
        ) from exc

    link = invite_link(token, dashboard_settings)
    send_invite_email(
        email_sender=email_sender,
        settings=settings,
        dashboard_settings=dashboard_settings,
        to_email=user.email,
        link=link,
    )

    return InviteDashboardAdminResponse(
        sent=True,
        user=build_admin_response(user),
        dev_invite_url=link if settings.app_env != "production" else None,
    )


@router.post("/accept")
def accept_dashboard_invite(
    payload: AcceptDashboardInviteRequest,
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
) -> OkResponse:
    user = setup_store.accept_dashboard_invite(
        token=payload.token,
        password=payload.password,
        now=int(time.time()),
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired admin invite.",
        )

    return OkResponse(ok=True)
