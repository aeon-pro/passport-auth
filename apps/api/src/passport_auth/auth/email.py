import json
import urllib.request
from typing import Protocol

from passport_auth.setup.store import DashboardSettings, EmailTemplate


class EmailDeliveryError(Exception):
    """Raised when an auth email cannot be delivered."""


class AuthEmailSender(Protocol):
    def send_template(
        self,
        *,
        template_key: str,
        to_email: str,
        values: dict[str, str],
        settings: DashboardSettings,
    ) -> None: ...


class ResendEmailSender:
    def send_template(
        self,
        *,
        template_key: str,
        to_email: str,
        values: dict[str, str],
        settings: DashboardSettings,
    ) -> None:
        if not settings.resend_api_key or not settings.resend_from_email:
            raise EmailDeliveryError("Resend is not configured.")

        template = _template_for_key(settings, template_key)
        subject = _render_template_text(template.subject, settings=settings, values=values)
        html = _render_email_html(template, settings=settings, values=values)
        payload = {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 400:
                    raise EmailDeliveryError("Resend rejected the auth email.")
        except OSError as exc:
            raise EmailDeliveryError("Resend could not deliver the auth email.") from exc


def _template_for_key(settings: DashboardSettings, key: str) -> EmailTemplate:
    for template in settings.email_templates:
        if template.key == key:
            return template

    raise EmailDeliveryError(f"Missing email template: {key}")


def _render_template_text(
    value: str,
    *,
    settings: DashboardSettings,
    values: dict[str, str],
) -> str:
    rendered = value.replace("{{brand_name}}", settings.brand_name or "Passport Auth")
    for key, replacement in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", replacement)
    return rendered


def _render_email_html(
    template: EmailTemplate,
    *,
    settings: DashboardSettings,
    values: dict[str, str],
) -> str:
    headline = _render_template_text(template.headline, settings=settings, values=values)
    body = _render_template_text(template.body, settings=settings, values=values)
    button = _render_template_text(template.button_label, settings=settings, values=values)
    footer = _render_template_text(template.footer_text, settings=settings, values=values)
    support_label = _render_template_text(template.support_label, settings=settings, values=values)
    support_url = _render_template_text(template.support_url, settings=settings, values=values)
    action_url = values.get("magic_link") or support_url
    logo_markup = _logo_markup(settings)
    body_style = (
        "margin:0;background:#f6f6f4;color:#111;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
    )
    shell_style = "max-width:640px;margin:0 auto;padding:56px 24px;text-align:center;"
    preheader_style = (
        "margin:0 0 20px;color:#777;font-size:12px;font-weight:700;"
        "letter-spacing:.08em;text-transform:uppercase;"
    )
    card_style = (
        "background:#fff;border:1px solid #deded8;border-radius:18px;"
        "padding:40px 32px;box-shadow:0 24px 80px rgba(20,20,18,.08);"
    )
    heading_style = (
        "margin:22px 0 12px;font-size:32px;line-height:1.08;"
        "font-weight:600;letter-spacing:-.03em;"
    )
    body_copy_style = (
        "margin:0 auto 26px;max-width:440px;color:#747474;"
        "font-size:16px;line-height:1.6;"
    )
    action_style = (
        f"display:inline-block;border-radius:10px;background:{template.accent_color};"
        "color:#111;padding:14px 18px;text-decoration:none;font-weight:700;"
    )
    footer_style = (
        "margin:0 auto 14px;max-width:440px;color:#9b9b9b;"
        "font-size:14px;line-height:1.55;"
    )
    support_style = "color:#111;font-weight:700;text-decoration:none;"

    return f"""
    <!doctype html>
    <html>
      <body style="{body_style}">
        <div style="{shell_style}">
          <p style="{preheader_style}">
            {escape_html(settings.brand_name)}
          </p>
          <div style="{card_style}">
            {logo_markup}
            <h1 style="{heading_style}">
              {escape_html(headline)}
            </h1>
            <p style="{body_copy_style}">
              {escape_html(body)}
            </p>
            <a href="{escape_html(action_url)}" style="{escape_html(action_style)}">
              {escape_html(button)}
            </a>
            <div style="height:1px;background:#e7e7e1;margin:32px 0 24px;"></div>
            <p style="{footer_style}">
              {escape_html(footer)}
            </p>
            <p style="margin:0;color:#9b9b9b;font-size:14px;">
              Need help?
              <a href="{escape_html(support_url)}" style="{support_style}">
                {escape_html(support_label)}
              </a>
            </p>
          </div>
        </div>
      </body>
    </html>
    """


def _logo_markup(settings: DashboardSettings) -> str:
    logo_url = settings.logo_url or settings.mark_url
    if logo_url:
        return (
            f'<img src="{escape_html(logo_url)}" alt="" '
            'style="width:46px;height:46px;object-fit:contain;border-radius:12px;" />'
        )

    initials = "".join(word[:1] for word in settings.brand_name.split()[:2]).upper() or "PA"
    return (
        '<div style="display:inline-grid;place-items:center;width:46px;height:46px;'
        'border-radius:12px;background:#1f1f23;color:#fff;font-weight:700;">'
        f"{escape_html(initials)}</div>"
    )


def escape_html(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )
