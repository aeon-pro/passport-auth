from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from passport_auth.core.config import Settings
from passport_auth.dashboard.tokens import (
    InvalidTokenError,
    create_dashboard_token,
    decode_dashboard_token,
)
from passport_auth.setup.passwords import verify_password
from passport_auth.setup.store import OwnerAccount, SetupStore

router = APIRouter(prefix="/dashboard/auth", tags=["dashboard-auth"])


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


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_setup_store(request: Request) -> SetupStore:
    return request.app.state.setup_store


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
        payload = decode_dashboard_token(token, secret=settings.app_encryption_key)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        ) from exc

    owner = setup_store.get_owner_by_email(str(payload["sub"]))
    if not owner or owner.role != payload["role"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    return owner


@router.post("/login")
def login(
    payload: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
) -> LoginResponse:
    owner = setup_store.get_owner_by_email(payload.email)
    if not owner or not verify_password(payload.password, owner.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_dashboard_token(
        email=owner.email,
        role=owner.role,
        secret=settings.app_encryption_key,
        ttl_seconds=settings.dashboard_jwt_ttl_seconds,
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=build_dashboard_user(owner),
    )


@router.get("/me")
def me(
    owner: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
) -> DashboardUserResponse:
    return build_dashboard_user(owner)
