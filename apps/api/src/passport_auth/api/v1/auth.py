import base64
import hashlib
import hmac
import secrets
import time
import urllib.parse
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from passport_auth.analytics import (
    PublicAuthAnalyticsEvent,
    analytics_email_identifier,
    analytics_origin,
    analytics_redirect_url,
    should_record_public_auth_analytics,
)
from passport_auth.auth.email import AuthEmailSender, EmailDeliveryError
from passport_auth.auth.google import GoogleOAuthClient, GoogleOAuthError
from passport_auth.auth.store import AuthStore, AuthUser, AuthUserAlreadyExistsError
from passport_auth.auth.tokens import create_public_access_token, decode_public_access_token
from passport_auth.core.config import Settings
from passport_auth.core.environment import (
    is_development_environment,
    is_local_development_url,
)
from passport_auth.core.rate_limit import RateLimiter, rate_limit_client
from passport_auth.dashboard.tokens import InvalidTokenError
from passport_auth.setup.passwords import verify_password
from passport_auth.setup.store import DashboardSettings, SetupStore

router = APIRouter(prefix="/auth", tags=["auth"])
DEFAULT_BLOCKED_MESSAGE = "This account is blocked. Contact support for more help."
RATE_LIMIT_DETAIL = "Too many authentication attempts. Try again later."
START_RATE_LIMIT = (3, 900)
VERIFY_RATE_LIMIT = (10, 600)
LOGIN_RATE_LIMIT = (5, 300)
TOKEN_RATE_LIMIT = (30, 300)


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
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_display_name(value)


class PasswordLoginRequest(AuthCodeRequest):
    password: str = Field(min_length=12, max_length=1024)


class RegisterVerifyRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    otp: str = Field(min_length=6, max_length=16)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("otp")
    @classmethod
    def strip_otp(cls, value: str) -> str:
        return value.strip()


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
    name: str
    email: str
    role: str
    email_verified: bool
    user_metadata: dict[str, Any]


class AuthCodeResponse(BaseModel):
    authorization_code: str
    redirect_url: str


class AuthRequestValidationResponse(BaseModel):
    ok: bool
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


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def enforce_auth_rate_limit(
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
    key = f"public-auth:{scope}:{client}:{subject.strip().lower()}"
    if not rate_limiter.hit(key, limit=limit, window_seconds=window_seconds):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMIT_DETAIL)


def request_origin(request: Request) -> str:
    return request.headers.get("Origin") or request.headers.get("Referer") or ""


def track_public_auth_event(
    *,
    request: Request,
    settings: Settings,
    event_type: str,
    auth_method: str = "",
    status_value: str = "success",
    user: AuthUser | None = None,
    email: str = "",
    redirect_url: str = "",
    reason: str = "",
    properties: dict[str, Any] | None = None,
) -> None:
    origin = request_origin(request)
    if not should_record_public_auth_analytics(
        settings,
        redirect_url=redirect_url,
        origin=origin,
    ):
        return

    request.app.state.analytics_sink.record_public_auth_event(
        PublicAuthAnalyticsEvent(
            event_type=event_type,
            auth_method=auth_method,
            status=status_value,
            user_id=user.id if user else "",
            email=analytics_email_identifier(
                user.email if user else email,
                secret=settings.app_encryption_key,
            ),
            redirect_url=analytics_redirect_url(redirect_url),
            origin=analytics_origin(origin),
            reason=reason,
            properties=properties or {},
        )
    )


def public_user_response(user: AuthUser) -> PublicUserResponse:
    return PublicUserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        email_verified=user.email_verified,
        user_metadata=user.user_metadata or {},
    )


def normalize_display_name(value: str) -> str:
    name = " ".join(value.strip().split())
    if not name:
        raise ValueError("Name is required.")
    return " ".join(word[:1].upper() + word[1:].lower() for word in name.split(" "))


def validate_redirect_url(
    dashboard_settings: DashboardSettings,
    redirect_url: str,
    *,
    app_env: str,
) -> None:
    if redirect_url in dashboard_settings.redirect_urls:
        return

    if any(
        registered_redirect_url_allows_query_params(registered_url, redirect_url)
        for registered_url in dashboard_settings.redirect_urls
    ):
        return

    if is_development_environment(app_env) and is_local_development_url(redirect_url):
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=redirect_url_error_detail(
            dashboard_settings,
            redirect_url,
            app_env=app_env,
        ),
    )


def registered_redirect_url_allows_query_params(registered_url: str, redirect_url: str) -> bool:
    registered = urllib.parse.urlsplit(registered_url)
    requested = urllib.parse.urlsplit(redirect_url)
    if registered.query or registered.fragment or requested.fragment:
        return False
    return bool(requested.query) and (
        registered.scheme.lower(),
        registered.netloc.lower(),
        registered.path,
    ) == (
        requested.scheme.lower(),
        requested.netloc.lower(),
        requested.path,
    )


def redirect_url_error_detail(
    dashboard_settings: DashboardSettings,
    redirect_url: str,
    *,
    app_env: str,
) -> str:
    configured = [url for url in dashboard_settings.redirect_urls if url]
    if configured:
        configured_text = ", ".join(configured[:5])
        if len(configured) > 5:
            configured_text = f"{configured_text}, ..."
        return (
            "Redirect URL is not allowed. "
            f"Received {redirect_url}. "
            f"Configured redirect URLs: {configured_text}."
        )

    if is_development_environment(app_env):
        return (
            "Redirect URL is not allowed. "
            f"Received {redirect_url}. "
            "Add this exact URL to Redirect URLs, or use a localhost URL in development."
        )

    return (
        "Redirect URL is not allowed. "
        f"Received {redirect_url}. "
        "Configure this exact URL in Passport Auth Settings."
    )


def validate_pkce_challenge(code_challenge: str) -> None:
    if not code_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing PKCE code challenge.",
        )
    if len(code_challenge) < 32:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PKCE code challenge is too short.",
        )
    if len(code_challenge) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PKCE code challenge is too long.",
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
    auth_method: str,
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
    auth_store.record_auth_activity(user_id=user.id, method=auth_method)
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
        private_key_pem=settings.resolved_public_jwt_private_key,
        issuer=settings.public_jwt_issuer,
        audience=settings.public_jwt_audience,
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


def get_or_create_public_user(
    auth_store: AuthStore,
    email: str,
    name: str | None = None,
) -> AuthUser:
    existing_user = auth_store.get_user_by_email(email)
    if existing_user:
        if name and not existing_user.name:
            return auth_store.update_user_profile(
                email=email,
                name=name,
                email_verified=True,
            ) or existing_user
        return existing_user
    return auth_store.create_user(email=email, name=name, email_verified=True)


def require_active_user(user: AuthUser) -> None:
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=user.blocked_message or DEFAULT_BLOCKED_MESSAGE,
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is deactivated.",
        )


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


@router.get("/request/validate")
def validate_auth_request(
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    redirect_url: str = Query(default="", max_length=2048),
    code_challenge: str = Query(default="", max_length=512),
) -> AuthRequestValidationResponse:
    redirect_url = redirect_url.strip()
    code_challenge = code_challenge.strip()
    if not redirect_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing redirect URL.",
        )

    validate_pkce_challenge(code_challenge)
    dashboard_settings = setup_store.get_dashboard_settings()
    validate_redirect_url(dashboard_settings, redirect_url, app_env=settings.app_env)
    return AuthRequestValidationResponse(ok=True, redirect_url=redirect_url)


@router.post("/register")
@router.post("/register/start")
def start_register(
    request: Request,
    payload: RegisterRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    email_sender: Annotated[AuthEmailSender, Depends(get_auth_email_sender)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> SendStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.password_login_enabled, "Password registration")
    validate_redirect_url(dashboard_settings, payload.redirect_url, app_env=settings.app_env)
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="register-start",
        subject=payload.email,
        limit=START_RATE_LIMIT[0],
        window_seconds=START_RATE_LIMIT[1],
    )

    if auth_store.get_user_by_email(payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    otp = f"{secrets.randbelow(1_000_000):06d}"
    auth_store.create_pending_registration(
        email=payload.email,
        name=payload.name,
        password=payload.password,
        redirect_url=payload.redirect_url,
        code_challenge=payload.code_challenge,
        otp=otp,
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
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="registration_started",
        auth_method="password",
        email=payload.email,
        redirect_url=payload.redirect_url,
    )
    return SendStartResponse(sent=True, dev_otp=otp if settings.app_env != "production" else None)


@router.post("/register/verify")
def verify_register(
    request: Request,
    payload: RegisterVerifyRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> AuthCodeResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.password_login_enabled, "Password registration")
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="register-verify",
        subject=payload.email,
        limit=VERIFY_RATE_LIMIT[0],
        window_seconds=VERIFY_RATE_LIMIT[1],
    )

    pending_registration = auth_store.consume_pending_registration(
        email=payload.email,
        otp=payload.otp,
        now=int(time.time()),
    )
    if not pending_registration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired registration code.",
        )

    validate_redirect_url(
        dashboard_settings,
        pending_registration.redirect_url,
        app_env=settings.app_env,
    )

    try:
        user = auth_store.create_user(
            email=pending_registration.email,
            name=pending_registration.name,
            password_hash=pending_registration.password_hash,
            email_verified=True,
        )
    except AuthUserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        ) from exc

    auth_code = issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        auth_method="password",
        redirect_url=pending_registration.redirect_url,
        code_challenge=pending_registration.code_challenge,
    )
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="registration_completed",
        auth_method="password",
        user=user,
        redirect_url=pending_registration.redirect_url,
    )
    return auth_code


@router.post("/password/login")
def password_login(
    request: Request,
    payload: PasswordLoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> AuthCodeResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.password_login_enabled, "Password login")
    validate_redirect_url(dashboard_settings, payload.redirect_url, app_env=settings.app_env)
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="password-login",
        subject=payload.email,
        limit=LOGIN_RATE_LIMIT[0],
        window_seconds=LOGIN_RATE_LIMIT[1],
    )

    user = auth_store.get_user_by_email(payload.email)
    if (
        not user
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="login_failure",
            auth_method="password",
            status_value="failure",
            email=payload.email,
            redirect_url=payload.redirect_url,
            reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    require_active_user(user)
    auth_code = issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        auth_method="password",
        redirect_url=payload.redirect_url,
        code_challenge=payload.code_challenge,
    )
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="login_success",
        auth_method="password",
        user=user,
        redirect_url=payload.redirect_url,
    )
    return auth_code


@router.post("/otp/start")
def start_otp(
    request: Request,
    payload: AuthCodeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    email_sender: Annotated[AuthEmailSender, Depends(get_auth_email_sender)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> SendStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.otp_login_enabled, "OTP login")
    validate_redirect_url(dashboard_settings, payload.redirect_url, app_env=settings.app_env)
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="otp-start",
        subject=payload.email,
        limit=START_RATE_LIMIT[0],
        window_seconds=START_RATE_LIMIT[1],
    )

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
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="otp_sent",
        auth_method="otp",
        email=payload.email,
        redirect_url=payload.redirect_url,
    )
    return SendStartResponse(sent=True, dev_otp=otp if settings.app_env != "production" else None)


@router.post("/otp/verify")
def verify_otp(
    request: Request,
    payload: OtpVerifyRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> AuthCodeResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.otp_login_enabled, "OTP login")
    validate_redirect_url(dashboard_settings, payload.redirect_url, app_env=settings.app_env)
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="otp-verify",
        subject=payload.email,
        limit=VERIFY_RATE_LIMIT[0],
        window_seconds=VERIFY_RATE_LIMIT[1],
    )

    if not auth_store.consume_otp(
        email=payload.email,
        otp=payload.otp,
        purpose="login",
        now=int(time.time()),
    ):
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="login_failure",
            auth_method="otp",
            status_value="failure",
            email=payload.email,
            redirect_url=payload.redirect_url,
            reason="invalid_otp",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP.",
        )

    user = get_or_create_public_user(auth_store, payload.email)
    require_active_user(user)
    auth_code = issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        auth_method="otp",
        redirect_url=payload.redirect_url,
        code_challenge=payload.code_challenge,
    )
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="login_success",
        auth_method="otp",
        user=user,
        redirect_url=payload.redirect_url,
    )
    return auth_code


@router.post("/magic-link/start")
def start_magic_link(
    request: Request,
    payload: AuthCodeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    email_sender: Annotated[AuthEmailSender, Depends(get_auth_email_sender)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> SendStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.magic_link_enabled, "Magic link")
    validate_redirect_url(dashboard_settings, payload.redirect_url, app_env=settings.app_env)
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="magic-link-start",
        subject=payload.email,
        limit=START_RATE_LIMIT[0],
        window_seconds=START_RATE_LIMIT[1],
    )

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
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="magic_link_sent",
        auth_method="magic_link",
        email=payload.email,
        redirect_url=payload.redirect_url,
    )
    return SendStartResponse(
        sent=True,
        dev_token=token if settings.app_env != "production" else None,
        dev_magic_link=magic_link_path(token) if settings.app_env != "production" else None,
    )


@router.post("/magic-link/consume")
def consume_magic_link(
    request: Request,
    payload: MagicLinkConsumeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> AuthCodeResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.magic_link_enabled, "Magic link")
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="magic-link-consume",
        subject=payload.token[:24],
        limit=VERIFY_RATE_LIMIT[0],
        window_seconds=VERIFY_RATE_LIMIT[1],
    )

    magic_link = auth_store.consume_magic_link(token=payload.token, now=int(time.time()))
    if not magic_link:
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="login_failure",
            auth_method="magic_link",
            status_value="failure",
            reason="invalid_magic_link",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired magic link.",
        )

    validate_redirect_url(dashboard_settings, magic_link.redirect_url, app_env=settings.app_env)
    user = get_or_create_public_user(auth_store, magic_link.email)
    require_active_user(user)
    auth_code = issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        auth_method="magic_link",
        redirect_url=magic_link.redirect_url,
        code_challenge=magic_link.code_challenge,
    )
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="login_success",
        auth_method="magic_link",
        user=user,
        redirect_url=magic_link.redirect_url,
    )
    return auth_code


@router.post("/password-reset/start")
def start_password_reset(
    request: Request,
    payload: PasswordResetStartRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    email_sender: Annotated[AuthEmailSender, Depends(get_auth_email_sender)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> SendStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.password_reset_otp_enabled, "Password reset OTP")
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="password-reset-start",
        subject=payload.email,
        limit=START_RATE_LIMIT[0],
        window_seconds=START_RATE_LIMIT[1],
    )

    user = auth_store.get_user_by_email(payload.email)
    if not user:
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="password_reset_started",
            auth_method="password_reset",
            email=payload.email,
            status_value="accepted",
            reason="unknown_email",
        )
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
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="password_reset_started",
        auth_method="password_reset",
        user=user,
    )
    return SendStartResponse(sent=True, dev_otp=otp if settings.app_env != "production" else None)


@router.post("/password-reset/confirm")
def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirmRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> OkResponse:
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="password-reset-confirm",
        subject=payload.email,
        limit=VERIFY_RATE_LIMIT[0],
        window_seconds=VERIFY_RATE_LIMIT[1],
    )
    if not auth_store.consume_otp(
        email=payload.email,
        otp=payload.otp,
        purpose="password_reset",
        now=int(time.time()),
    ):
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="password_reset_failed",
            auth_method="password_reset",
            email=payload.email,
            status_value="failure",
            reason="invalid_otp",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    auth_store.update_user_password(email=payload.email, password=payload.password)
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="password_reset_completed",
        auth_method="password_reset",
        email=payload.email,
    )
    return OkResponse(ok=True)


@router.get("/google/start")
def start_google_oauth(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    google_client: Annotated[GoogleOAuthClient, Depends(get_google_oauth_client)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    redirect_url: str = Query(min_length=8, max_length=2048),
    code_challenge: str = Query(min_length=32, max_length=256),
) -> GoogleStartResponse:
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.google_oauth_enabled, "Google OAuth")
    validate_redirect_url(dashboard_settings, redirect_url, app_env=settings.app_env)
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="google-start",
        subject=redirect_url,
        limit=TOKEN_RATE_LIMIT[0],
        window_seconds=TOKEN_RATE_LIMIT[1],
    )
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
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="google_oauth_started",
        auth_method="google",
        redirect_url=redirect_url,
    )
    return GoogleStartResponse(
        authorization_url=google_client.authorization_url(
            state=state,
            settings=dashboard_settings,
        )
    )


@router.get("/google/callback")
def complete_google_oauth(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    setup_store: Annotated[SetupStore, Depends(get_setup_store)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    google_client: Annotated[GoogleOAuthClient, Depends(get_google_oauth_client)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    state: str = Query(min_length=20, max_length=512),
    code: str = Query(min_length=1, max_length=2048),
    response: str = Query(default="redirect", max_length=16),
):
    dashboard_settings = setup_store.get_dashboard_settings()
    require_method(dashboard_settings.google_oauth_enabled, "Google OAuth")
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="google-callback",
        subject=state[:24],
        limit=TOKEN_RATE_LIMIT[0],
        window_seconds=TOKEN_RATE_LIMIT[1],
    )
    oauth_state = auth_store.consume_oauth_state(state=state, now=int(time.time()))
    if not oauth_state:
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="login_failure",
            auth_method="google",
            status_value="failure",
            reason="invalid_oauth_state",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state.",
        )
    validate_redirect_url(dashboard_settings, oauth_state.redirect_url, app_env=settings.app_env)

    try:
        profile = google_client.exchange_code(code=code, settings=dashboard_settings)
    except GoogleOAuthError as exc:
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="login_failure",
            auth_method="google",
            status_value="failure",
            redirect_url=oauth_state.redirect_url,
            reason="provider_error",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    email = str(profile.get("email") or "").strip().lower()
    if not email:
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="login_failure",
            auth_method="google",
            status_value="failure",
            redirect_url=oauth_state.redirect_url,
            reason="missing_email",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return an email address.",
        )

    google_name = str(profile.get("name") or "").strip()
    user = get_or_create_public_user(
        auth_store,
        email,
        name=normalize_display_name(google_name) if google_name else None,
    )
    require_active_user(user)
    auth_code = issue_auth_code(
        auth_store=auth_store,
        settings=settings,
        user=user,
        auth_method="google",
        redirect_url=oauth_state.redirect_url,
        code_challenge=oauth_state.code_challenge,
    )
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="login_success",
        auth_method="google",
        user=user,
        redirect_url=oauth_state.redirect_url,
    )
    if response == "json":
        return auth_code
    return redirect_with_code(auth_code.redirect_url, auth_code.authorization_code)


@router.post("/token")
def exchange_token(
    request: Request,
    payload: TokenExchangeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> TokenResponse:
    enforce_auth_rate_limit(
        request=request,
        rate_limiter=rate_limiter,
        scope="token-exchange",
        subject=payload.code[:24],
        limit=TOKEN_RATE_LIMIT[0],
        window_seconds=TOKEN_RATE_LIMIT[1],
    )
    auth_code = auth_store.consume_auth_code(code=payload.code, now=int(time.time()))
    if not auth_code or not verify_pkce(payload.code_verifier, auth_code.code_challenge):
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="token_exchange_failure",
            status_value="failure",
            reason="invalid_code_or_pkce",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired authorization code.",
        )

    user = auth_store.get_user_by_id(auth_code.user_id)
    if not user:
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="token_exchange_failure",
            status_value="failure",
            redirect_url=auth_code.redirect_url,
            reason="missing_user",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active.",
        )
    require_active_user(user)

    token_pair = issue_token_pair(auth_store=auth_store, settings=settings, user=user)
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="token_exchange",
        user=user,
        redirect_url=auth_code.redirect_url,
    )
    return token_pair


@router.post("/refresh")
def refresh(
    request: Request,
    payload: RefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> TokenResponse:
    refresh_token = auth_store.consume_refresh_token(
        token=payload.refresh_token,
        now=int(time.time()),
    )
    if not refresh_token:
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="token_refresh_failure",
            status_value="failure",
            reason="invalid_refresh_token",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user = auth_store.get_user_by_id(refresh_token.user_id)
    if not user:
        track_public_auth_event(
            request=request,
            settings=settings,
            event_type="token_refresh_failure",
            status_value="failure",
            reason="missing_user",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active.",
        )
    require_active_user(user)

    token_pair = issue_token_pair(auth_store=auth_store, settings=settings, user=user)
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="token_refresh",
        user=user,
    )
    return token_pair


@router.post("/logout")
def logout(
    request: Request,
    payload: LogoutRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_store: Annotated[AuthStore, Depends(get_auth_store)],
) -> OkResponse:
    auth_store.revoke_refresh_token(token=payload.refresh_token)
    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="logout",
    )
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
        payload = decode_public_access_token(
            token,
            public_key_pem=settings.public_jwt_public_key_pem,
            issuer=settings.public_jwt_issuer,
            audience=settings.public_jwt_audience,
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        ) from exc

    user = auth_store.get_user_by_id(str(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    require_active_user(user)

    track_public_auth_event(
        request=request,
        settings=settings,
        event_type="active_user",
        user=user,
    )
    return public_user_response(user)
