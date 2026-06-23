import secrets
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from passport_auth.core.config import Settings
from passport_auth.core.rate_limit import RateLimiter, rate_limit_client
from passport_auth.dashboard.tokens import (
    InvalidTokenError,
    create_dashboard_token,
    decode_dashboard_token,
)
from passport_auth.setup.passwords import verify_password
from passport_auth.setup.store import OwnerAccount, SetupStore

router = APIRouter(prefix="/dashboard/auth", tags=["dashboard-auth"])
RATE_LIMIT_DETAIL = "Too many authentication attempts. Try again later."


class DashboardUserResponse(BaseModel):
    email: str
    role: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: DashboardUserResponse


class PasswordResetStartRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PasswordResetStartResponse(BaseModel):
    sent: bool
    dev_otp: str | None = None


class PasswordResetConfirmRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    otp: str = Field(min_length=6, max_length=16)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class OkResponse(BaseModel):
    ok: bool


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_setup_store(request: Request) -> SetupStore:
    return request.app.state.setup_store


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def enforce_dashboard_rate_limit(
    *,
    request: Request,
    rate_limiter: RateLimiter,
    scope: str,
    subject: str,
    limit: int,
    window_seconds: int,
) -> None:
    client_host = request.client.host if request.client else None
    client = rate_limit_client(request.headers, client_host)
    key = f"dashboard-auth:{scope}:{client}:{subject.strip().lower()}"
    if not rate_limiter.hit(key, limit=limit, window_seconds=window_seconds):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMIT_DETAIL)


def build_dashboard_user(owner: OwnerAccount) -> DashboardUserResponse:
    return DashboardUserResponse(email=owner.email, role=owner.role)


def get_current_dashboard_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
) -> OwnerAccount:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    try:
        payload = decode_dashboard_token(token, secret=settings.resolved_dashboard_jwt_secret)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        ) from exc

    owner = setup_store.get_dashboard_user_by_email(str(payload["sub"]))
    if not owner or not owner.accepted_at or owner.role != payload["role"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    return owner


def require_owner(
    user: OwnerAccount,
    detail: str = "Only the owner can manage this dashboard resource.",
) -> None:
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


@router.post("/login")
def login(
    request: Request,
    payload: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> LoginResponse:
    enforce_dashboard_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="login",
        subject=payload.email,
        limit=5,
        window_seconds=300,
    )
    owner = setup_store.get_dashboard_user_by_email(payload.email)
    if (
        not owner
        or not owner.accepted_at
        or not verify_password(payload.password, owner.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_dashboard_token(
        email=owner.email,
        role=owner.role,
        secret=settings.resolved_dashboard_jwt_secret,
        ttl_seconds=settings.dashboard_jwt_ttl_seconds,
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=build_dashboard_user(owner),
    )


@router.post("/password-reset/start")
def start_password_reset(
    request: Request,
    payload: PasswordResetStartRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> PasswordResetStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    if not settings.password_reset_otp_enabled or not dashboard_settings.password_reset_otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Password reset is disabled.",
        )
    enforce_dashboard_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="password-reset-start",
        subject=payload.email,
        limit=3,
        window_seconds=900,
    )

    owner = setup_store.get_dashboard_user_by_email(payload.email)
    if not owner:
        return PasswordResetStartResponse(sent=True)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    setup_store.create_password_reset_otp(
        email=owner.email,
        otp=otp,
        expires_at=int(time.time()) + settings.password_reset_otp_ttl_seconds,
    )

    return PasswordResetStartResponse(
        sent=True,
        dev_otp=otp if settings.app_env != "production" else None,
    )


@router.post("/password-reset/confirm")
def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirmRequest,
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> OkResponse:
    enforce_dashboard_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="password-reset-confirm",
        subject=payload.email,
        limit=10,
        window_seconds=600,
    )
    owner = setup_store.get_dashboard_user_by_email(payload.email)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    is_valid_otp = setup_store.consume_password_reset_otp(
        email=owner.email,
        otp=payload.otp,
        now=int(time.time()),
    )
    if not is_valid_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    setup_store.update_dashboard_user_password(email=owner.email, password=payload.password)
    return OkResponse(ok=True)


@router.get("/me")
def me(
    owner: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
) -> DashboardUserResponse:
    return build_dashboard_user(owner)
