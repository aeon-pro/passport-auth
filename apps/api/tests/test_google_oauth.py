import base64
import json

import pytest

from passport_auth.auth.google import UrlLibGoogleOAuthClient
from passport_auth.setup.store import DashboardSettings


class FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def id_token_payload(payload: dict[str, object]) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode("ascii")
    return f"header.{encoded}.signature"


def test_google_oauth_client_returns_name_from_id_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: int):
        assert timeout == 10
        assert request.full_url == "https://oauth2.googleapis.com/token"
        return FakeResponse(
            {
                "access_token": "google-access-token",
                "id_token": id_token_payload(
                    {
                        "email": "Google.User@example.com",
                        "name": "Google User",
                    }
                ),
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    profile = UrlLibGoogleOAuthClient().exchange_code(
        code="provider-code",
        settings=DashboardSettings(
            app_domain="app.example.com",
            auth_domain="auth.example.com",
            google_client_id="google-client-id",
            google_client_secret="google-secret",
        ),
    )

    assert profile == {"email": "google.user@example.com", "name": "Google User"}
