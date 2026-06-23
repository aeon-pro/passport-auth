import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator

from passport_auth.api.v1.dashboard_auth import get_current_dashboard_user, require_owner
from passport_auth.auth.store import AuthStore, AuthUser, AuthUserAlreadyExistsError
from passport_auth.setup.store import OwnerAccount

router = APIRouter(prefix="/dashboard/users", tags=["dashboard-users"])

ALLOWED_USER_ROLES = {"owner", "admin", "user"}
MAX_METADATA_BYTES = 16_384
MAX_BLOCKED_MESSAGE_LENGTH = 500


class DashboardUserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime
    name: str
    role: str
    is_active: bool
    email_verified: bool
    is_blocked: bool
    blocked_message: str
    first_auth_method: str
    last_login_at: datetime | None
    last_auth_method: str
    login_count: int
    user_metadata: dict[str, Any]


class DashboardUsersResponse(BaseModel):
    users: list[DashboardUserResponse]
    total: int


class OkResponse(BaseModel):
    ok: bool


class DashboardUserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    email_verified: bool | None = None
    is_blocked: bool | None = None
    blocked_message: str | None = Field(default=None, max_length=MAX_BLOCKED_MESSAGE_LENGTH)
    user_metadata: dict[str, Any] | None = None

    @field_validator("email", "name", "role", "blocked_message")
    @classmethod
    def strip_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in ALLOWED_USER_ROLES:
            raise ValueError("Role must be owner, admin, or user.")
        return normalized

    @field_validator("user_metadata")
    @classmethod
    def validate_user_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        encoded = json.dumps(value, separators=(",", ":"), sort_keys=True)
        if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
            raise ValueError("User metadata must be 16 KB or smaller.")
        return value


def get_auth_store(request: Request) -> AuthStore:
    return request.app.state.auth_store


def build_user_response(user: AuthUser) -> DashboardUserResponse:
    return DashboardUserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        email_verified=user.email_verified,
        is_blocked=user.is_blocked,
        blocked_message=user.blocked_message,
        first_auth_method=user.first_auth_method,
        last_login_at=user.last_login_at,
        last_auth_method=user.last_auth_method,
        login_count=user.login_count,
        user_metadata=user.user_metadata or {},
    )


@router.get("")
def list_dashboard_users(
    owner: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    query: str = Query(default="", max_length=120),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DashboardUsersResponse:
    require_owner(owner)
    users, total = auth_store.list_users(query=query, limit=limit, offset=offset)
    return DashboardUsersResponse(
        users=[build_user_response(user) for user in users],
        total=total,
    )


@router.patch("/{user_id}")
def update_dashboard_user(
    user_id: str,
    payload: DashboardUserUpdate,
    owner: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> DashboardUserResponse:
    require_owner(owner)
    updates = payload.model_dump(exclude_unset=True)
    try:
        user = auth_store.update_user(user_id=user_id, **updates)
    except AuthUserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        ) from exc

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return build_user_response(user)


@router.delete("/{user_id}")
def delete_dashboard_user(
    user_id: str,
    owner: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> OkResponse:
    require_owner(owner)
    if not auth_store.delete_user(user_id=user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return OkResponse(ok=True)
