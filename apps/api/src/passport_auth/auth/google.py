import base64
import json
import urllib.parse
import urllib.request
from typing import Protocol

from passport_auth.setup.store import DashboardSettings


class GoogleOAuthError(Exception):
    """Raised when the Google OAuth provider cannot complete the flow."""


class GoogleOAuthClient(Protocol):
    def authorization_url(self, *, state: str, settings: DashboardSettings) -> str: ...

    def exchange_code(self, *, code: str, settings: DashboardSettings) -> dict[str, str]: ...


class UrlLibGoogleOAuthClient:
    def authorization_url(self, *, state: str, settings: DashboardSettings) -> str:
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": google_redirect_uri(settings),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

    def exchange_code(self, *, code: str, settings: DashboardSettings) -> dict[str, str]:
        if not settings.google_client_id or not settings.google_client_secret:
            raise GoogleOAuthError("Google OAuth is not configured.")

        token_payload = urllib.parse.urlencode(
            {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": google_redirect_uri(settings),
            }
        ).encode("utf-8")
        token_request = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(token_request, timeout=10) as response:
                token_body = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            raise GoogleOAuthError("Google OAuth token exchange failed.") from exc

        access_token = str(token_body.get("access_token") or "")
        id_token = str(token_body.get("id_token") or "")
        profile = _profile_from_id_token(id_token)
        if access_token and (not profile.get("email") or not profile.get("name")):
            userinfo_profile = _profile_from_userinfo(access_token)
            id_token_profile = {key: value for key, value in profile.items() if value}
            profile = {**userinfo_profile, **id_token_profile}

        email = str(profile.get("email") or "").strip().lower()
        if not email:
            raise GoogleOAuthError("Google did not return an email address.")

        return {
            "email": email,
            "name": str(profile.get("name") or "").strip(),
        }


def google_redirect_uri(settings: DashboardSettings) -> str:
    origin = _origin_from_domain(settings.auth_domain or settings.app_domain)
    return f"{origin}/api/v1/auth/google/callback"


def _origin_from_domain(domain: str) -> str:
    cleaned = domain.strip().rstrip("/")
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://{cleaned or 'localhost:8000'}"


def _profile_from_id_token(id_token: str) -> dict[str, str]:
    parts = id_token.split(".")
    if len(parts) < 2:
        return {}

    try:
        payload = json.loads(_base64url_decode(parts[1]).decode("utf-8"))
    except (ValueError, TypeError):
        return {}

    return {
        "email": str(payload.get("email") or "").strip().lower(),
        "name": str(payload.get("name") or "").strip(),
    }


def _profile_from_userinfo(access_token: str) -> dict[str, str]:
    request = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise GoogleOAuthError("Google user profile fetch failed.") from exc

    return {
        "email": str(body.get("email") or "").strip().lower(),
        "name": str(body.get("name") or "").strip(),
    }


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))
