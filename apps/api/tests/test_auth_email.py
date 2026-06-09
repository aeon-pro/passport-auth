import io
import json
import urllib.error

import pytest

from passport_auth.auth.email import EmailDeliveryError, ResendEmailSender
from passport_auth.setup.store import DashboardSettings


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
            settings=DashboardSettings(
                resend_from_email="Alactic <auth@mail.alactic.net>",
                resend_api_key="re_test_key",
                brand_name="Alactic",
            ),
        )
