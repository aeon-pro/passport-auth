import base64
import hashlib
import hmac
import secrets
import time
import urllib.parse
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from passport_auth.auth.email import AuthEmailSender, EmailDeliveryError
from passport_auth.auth.google import GoogleOAuthClient, GoogleOAuthError
from passport_auth.auth.store import AuthStore, AuthUser, AuthUserAlreadyExistsError
from passport_auth.auth.tokens import create_public_access_token, decode_public_access_token
from passport_auth.core.config import Settings
from passport_auth.dashboard.tokens import InvalidTokenError
from passport_auth.setup.passwords import verify_password
from passport_auth.setup.store import DashboardSettings, SetupStore

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    redirect_url: str = Field(min_length=8, max_length=2048)
    code_challenge: str = Field(min_length=32, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("redirect_url", "code_challenge")
    @classmethod
    def strip_string(cls, value: str) -> str:
        return value.strip()


class RegisterRequest(AuthCodeRequest):
    password: str = Field(min_length=12, max_length=1024)


class PasswordLoginRequest(RegisterRequest):
    pass


class OtpVerifyRequest(AuthCodeRequest):
    otp: str = Field(min_length=6, max_length=16)

    @field_validator("otp")
    @classmethod
    def strip_otp(cls, value: str) -> str:
        return value.strip()


class MagicLinkConsumeRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)

    @field_validator("token")
    @classmethod
    def strip_token(cls, value: str) -> str:
        return value.strip()


class TokenExchangeRequest(BaseModel):
    code: str = Field(min_length=20, max_length=512)
    code_verifier: str = Field(min_length=32, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=512)


class LogoutRequest(RefreshRequest):
    pass


class PasswordResetStartRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PasswordResetConfirmRequest(PasswordResetStartRequest):
    otp: str = Field(min_length=6, max_length=16)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("otp")
    @classmethod
    def strip_otp(cls, value: str) -> str:
        return value.strip()


class PublicUserResponse(BaseModel):
    id: str
    email: str
    role: str


class AuthCodeResponse(BaseModel):
    authorization_code: str
    redirect_url: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: PublicUserResponse


class SendStartResponse(BaseModel):
    sent: bool
    dev_otp: str | None = None
    dev_token: str | None = None
    dev_magic_link: str | None = None


class GoogleStartResponse(BaseModel):
    authorization_url: str


class OkResponse(BaseModel):
    ok: bool


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_setup_store(request: Request) -> SetupStore:
    return request.app.state.setup_store


def get_auth_store(request: Request) -> AuthStore:
    return request.app.state.auth_store


def get_auth_email_sender(request: Request) -> AuthEmailSender:
    return request.app.state.auth_email_sender


def get_google_oauth_client(request: Request) -> GoogleOAuthClient:
    return request.app.state.google_oauth_client


def public_user_response(user: AuthUser) -> PublicUserResponse:
    return PublicUserResponse(id=user.id, email=user.email, role=user.role)


def validate_redirect_url(settings: DashboardSettings, redirect_url: str) -> None:
    if redirect_url not in settings.redirect_urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Redirect URL is not allowed.",
        )


def require_method(enabled: bool, method_name: str) -> None:
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{method_name} is disabled.",
        )


def issue_auth_code(
    *,
    auth_store: AuthStore,
    settings: Settings,
    user: AuthUser,
    redirect_url: str,
    code_challenge: str,
) -> AuthCodeResponse:
    code = secrets.token_urlsafe(48)
    auth_store.create_auth_code(
        code=code,
        user_id=user.id,
        redirect_url=redirect_url,
        code_challenge=code_challenge,
        expires_at=int(time.time()) + settings.public_auth_code_ttl_seconds,
    )
    return AuthCodeResponse(authorization_code=code, redirect_url=redirect_url)


def issue_token_pair(
    *,
    auth_store: AuthStore,
    settings: Settings,
    user: AuthUser,
) -> TokenResponse:
    refresh_token = secrets.token_urlsafe(64)
    auth_store.create_refresh_token(
        token=refresh_token,
        user_id=user.id,
        expires_at=int(time.time()) + settings.public_refresh_token_ttl_seconds,
    )
    access_token = create_public_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        secret=settings.app_encryption_key,
        ttl_seconds=settings.public_access_token_ttl_seconds,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.public_access_token_ttl_seconds,
        user=public_user_response(user),
    )


def verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(expected, code_challenge)


def get_or_create_public_user(auth_store: AuthStore, email: str) -> AuthUser:
    existing_user = auth_store.get_user_by_email(email)
    if existing_user:
        return existing_user
    return auth_store.create_user(email=email)


def send_auth_email(
    *,
    email_sender: AuthEmailSender,
    settings: Settings,
    dashboard_settings: DashboardSettings,
    template_key: str,
    to_email: str,
    values: dict[str, str],
) -> None:
    if settings.app_env != "production" and not dashboard_settings.resend_api_key:
        return

    try:
        email_sender.send_template(
            template_key=template_key,
            to_email=to_email,
            values=values,
            settings=dashboard_settings,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def auth_origin(dashboard_settings: DashboardSettings) -> str:
    domain = (dashboard_settings.auth_domain or dashboard_settings.app_domain).strip().rstrip("/")
    if not domain:
        return ""
    if domain.startswith(("http://", "https://")):
        return domain
    return f"https://{domain}"


def magic_link_path(token: str) -> str:
    return f"/verify?token={urllib.parse.quote(token)}"


def magic_link_url(token: str, dashboard_settings: DashboardSettings) -> str:
    origin = auth_origin(dashboard_settings)
    path = magic_link_path(token)
    return f"{origin}{path}" if origin else path


def redirect_with_code(redirect_url: str, authorization_code: str) -> RedirectResponse:
    parts = urllib.parse.urlsplit(redirect_url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("code", authorization_code))
    return RedirectResponse(
        urllib.parse.urlunsplit(
            parts._replace(query=urllib.parse.urlencode(query)),
        )
    )


@router.post("/register")
def register(
    payload: RegisterRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> AuthCodeResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.password_login_enabled, "Password registration")
    validate_redirect_url(dashboard_settings, payload.redirect_url)

    try:
        user = auth_store.create_user(email=payload.email, password=payload.password)
    except AuthUserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        ) from exc

    return issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        redirect_url=payload.redirect_url,
        code_challenge=payload.code_challenge,
    )


@router.post("/password/login")
def password_login(
    payload: PasswordLoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> AuthCodeResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.password_login_enabled, "Password login")
    validate_redirect_url(dashboard_settings, payload.redirect_url)

    user = auth_store.get_user_by_email(payload.email)
    if (
        not user
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        redirect_url=payload.redirect_url,
        code_challenge=payload.code_challenge,
    )


@router.post("/otp/start")
def start_otp(
    payload: AuthCodeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    email_sender: Annotated[AuthEmailSender, Depends(get_auth_email_sender)],
) -> SendStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.otp_login_enabled, "OTP login")
    validate_redirect_url(dashboard_settings, payload.redirect_url)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    auth_store.create_otp(
        email=payload.email,
        otp=otp,
        purpose="login",
        expires_at=int(time.time()) + settings.public_otp_ttl_seconds,
    )
    send_auth_email(
        email_sender=email_sender,
        settings=settings,
        dashboard_settings=dashboard_settings,
        template_key="otp",
        to_email=payload.email,
        values={"code": otp},
    )
    return SendStartResponse(sent=True, dev_otp=otp if settings.app_env != "production" else None)


@router.post("/otp/verify")
def verify_otp(
    payload: OtpVerifyRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> AuthCodeResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.otp_login_enabled, "OTP login")
    validate_redirect_url(dashboard_settings, payload.redirect_url)

    if not auth_store.consume_otp(
        email=payload.email,
        otp=payload.otp,
        purpose="login",
        now=int(time.time()),
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP.",
        )

    user = get_or_create_public_user(auth_store, payload.email)
    return issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        redirect_url=payload.redirect_url,
        code_challenge=payload.code_challenge,
    )


@router.post("/magic-link/start")
def start_magic_link(
    payload: AuthCodeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    email_sender: Annotated[AuthEmailSender, Depends(get_auth_email_sender)],
) -> SendStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.magic_link_enabled, "Magic link")
    validate_redirect_url(dashboard_settings, payload.redirect_url)

    token = secrets.token_urlsafe(48)
    auth_store.create_magic_link(
        token=token,
        email=payload.email,
        redirect_url=payload.redirect_url,
        code_challenge=payload.code_challenge,
        expires_at=int(time.time()) + settings.public_magic_link_ttl_seconds,
    )
    send_auth_email(
        email_sender=email_sender,
        settings=settings,
        dashboard_settings=dashboard_settings,
        template_key="magic_link",
        to_email=payload.email,
        values={"magic_link": magic_link_url(token, dashboard_settings)},
    )
    return SendStartResponse(
        sent=True,
        dev_token=token if settings.app_env != "production" else None,
        dev_magic_link=magic_link_path(token) if settings.app_env != "production" else None,
    )


@router.post("/magic-link/consume")
def consume_magic_link(
    payload: MagicLinkConsumeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> AuthCodeResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.magic_link_enabled, "Magic link")

    magic_link = auth_store.consume_magic_link(token=payload.token, now=int(time.time()))
    if not magic_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired magic link.",
        )

    validate_redirect_url(dashboard_settings, magic_link.redirect_url)
    user = get_or_create_public_user(auth_store, magic_link.email)
    return issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        redirect_url=magic_link.redirect_url,
        code_challenge=magic_link.code_challenge,
    )


@router.post("/password-reset/start")
def start_password_reset(
    payload: PasswordResetStartRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    email_sender: Annotated[AuthEmailSender, Depends(get_auth_email_sender)],
) -> SendStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.password_reset_otp_enabled, "Password reset OTP")

    user = auth_store.get_user_by_email(payload.email)
    if not user:
        return SendStartResponse(sent=True)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    auth_store.create_otp(
        email=user.email,
        otp=otp,
        purpose="password_reset",
        expires_at=int(time.time()) + settings.public_otp_ttl_seconds,
    )
    send_auth_email(
        email_sender=email_sender,
        settings=settings,
        dashboard_settings=dashboard_settings,
        template_key="password_reset",
        to_email=user.email,
        values={"code": otp},
    )
    return SendStartResponse(sent=True, dev_otp=otp if settings.app_env != "production" else None)


@router.post("/password-reset/confirm")
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> OkResponse:
    if not auth_store.consume_otp(
        email=payload.email,
        otp=payload.otp,
        purpose="password_reset",
        now=int(time.time()),
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    auth_store.update_user_password(email=payload.email, password=payload.password)
    return OkResponse(ok=True)


@router.get("/google/start")
def start_google_oauth(
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    google_client: Annotated[GoogleOAuthClient, Depends(get_google_oauth_client)],
    redirect_url: str = Query(min_length=8, max_length=2048),
    code_challenge: str = Query(min_length=32, max_length=256),
) -> GoogleStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.google_oauth_enabled, "Google OAuth")
    validate_redirect_url(dashboard_settings, redirect_url)
    if not dashboard_settings.google_client_id or not dashboard_settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured.",
        )

    state = secrets.token_urlsafe(48)
    auth_store.create_oauth_state(
        state=state,
        redirect_url=redirect_url,
        code_challenge=code_challenge,
        expires_at=int(time.time()) + settings.public_oauth_state_ttl_seconds,
    )
    return GoogleStartResponse(
        authorization_url=google_client.authorization_url(
            state=state,
            settings=dashboard_settings,
        )
    )


@router.get("/google/callback")
def complete_google_oauth(
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    google_client: Annotated[GoogleOAuthClient, Depends(get_google_oauth_client)],
    state: str = Query(min_length=20, max_length=512),
    code: str = Query(min_length=1, max_length=2048),
    response: str = Query(default="redirect", max_length=16),
):
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.google_oauth_enabled, "Google OAuth")
    oauth_state = auth_store.consume_oauth_state(state=state, now=int(time.time()))
    if not oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state.",
        )
    validate_redirect_url(dashboard_settings, oauth_state.redirect_url)

    try:
        profile = google_client.exchange_code(code=code, settings=dashboard_settings)
    except GoogleOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    email = str(profile.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return an email address.",
        )

    user = get_or_create_public_user(auth_store, email)
    auth_code = issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        redirect_url=oauth_state.redirect_url,
        code_challenge=oauth_state.code_challenge,
    )
    if response == "json":
        return auth_code
    return redirect_with_code(auth_code.redirect_url, auth_code.authorization_code)


@router.post("/token")
def exchange_token(
    payload: TokenExchangeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> TokenResponse:
    auth_code = auth_store.consume_auth_code(code=payload.code, now=int(time.time()))
    if not auth_code or not verify_pkce(payload.code_verifier, auth_code.code_challenge):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired authorization code.",
        )

    user = auth_store.get_user_by_id(auth_code.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active.",
        )

    return issue_token_pair(auth_store=auth_store, settings=settings, user=user)


@router.post("/refresh")
def refresh(
    payload: RefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> TokenResponse:
    refresh_token = auth_store.consume_refresh_token(
        token=payload.refresh_token,
        now=int(time.time()),
    )
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user = auth_store.get_user_by_id(refresh_token.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active.",
        )

    return issue_token_pair(auth_store=auth_store, settings=settings, user=user)


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> OkResponse:
    auth_store.revoke_refresh_token(token=payload.refresh_token)
    return OkResponse(ok=True)


@router.get("/me")
def me(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> PublicUserResponse:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    try:
        payload = decode_public_access_token(token, secret=settings.app_encryption_key)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        ) from exc

    user = auth_store.get_user_by_id(str(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    return public_user_response(user)
