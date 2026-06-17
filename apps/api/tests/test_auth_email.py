import io
import json
import urllib.error

import pytest

from passport_auth.auth.email import EmailDeliveryError, ResendEmailSender
from passport_auth.setup.store import DashboardSettings


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


def resend_settings() -> DashboardSettings:
    return DashboardSettings(
        resend_from_email="Alactic <auth@mail.alactic.net>",
        resend_api_key="re_test_key",
        brand_name="Alactic",
    )


def test_resend_sender_identifies_server_client(monkeypatch: pytest.MonkeyPatch) -> None:
    def accept_email(request, timeout: int):
        assert timeout == 10
        assert request.get_header("User-agent", "").startswith("PassportAuth/")
        assert request.get_header("Accept") == "application/json"
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", accept_email)

    ResendEmailSender().send_template(
        template_key="otp",
        to_email="user@example.com",
        values={"code": "123456"},
        settings=resend_settings(),
    )


def test_resend_sender_surfaces_rejection_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_email(_request, timeout: int):
        assert timeout == 10
        body = json.dumps({"message": "The from domain is not verified."}).encode()
        raise urllib.error.HTTPError(
            url="https://api.resend.com/emails",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=io.BytesIO(body),
        )

    monkeypatch.setattr("urllib.request.urlopen", reject_email)

    with pytest.raises(EmailDeliveryError, match="The from domain is not verified"):
        ResendEmailSender().send_template(
            template_key="otp",
            to_email="user@example.com",
            values={"code": "123456"},
            settings=resend_settings(),
        )


def test_resend_email_logo_uses_contrast_tile(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_payload = {}

    def accept_email(request, timeout: int):
        assert timeout == 10
        captured_payload.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", accept_email)

    ResendEmailSender().send_template(
        template_key="otp",
        to_email="user@example.com",
        values={"code": "123456"},
        settings=DashboardSettings(
            resend_from_email="Alactic <auth@mail.alactic.net>",
            resend_api_key="re_test_key",
            brand_name="Alactic",
            logo_url="https://auth.alactic.net/dashboard-assets/logos/white-logo.png",
        ),
    )

    html = captured_payload["html"]
    assert "background:#17171a" in html
    assert "white-logo.png" in html
    assert "vertical-align:middle" in html
