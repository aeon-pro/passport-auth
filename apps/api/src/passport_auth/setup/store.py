import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol
from uuid import uuid4

from passport_auth.setup.passwords import hash_password, verify_password
from passport_auth.setup.secrets import decrypt_secret, encrypt_secret


class SetupAlreadyCompleteError(Exception):
    """Raised when an owner account already exists."""


@dataclass(frozen=True)
class OwnerAccount:
    email: str
    password_hash: str
    role: str = "owner"


@dataclass(frozen=True)
class PasswordResetOtp:
    email: str
    otp_hash: str
    expires_at: int


@dataclass(frozen=True)
class EmailTemplate:
    key: str
    name: str
    subject: str
    headline: str
    body: str
    button_label: str
    accent_color: str


DEFAULT_EMAIL_TEMPLATES = (
    EmailTemplate(
        key="magic_link",
        name="Magic link",
        subject="Sign in to {{brand_name}}",
        headline="Your sign-in link is ready",
        body="Use the secure link below to finish signing in. The link expires soon.",
        button_label="Open magic link",
        accent_color="#f5f5f7",
    ),
    EmailTemplate(
        key="otp",
        name="One-time passcode",
        subject="Your {{brand_name}} verification code",
        headline="Your verification code",
        body="Enter {{code}} to continue. This code expires soon.",
        button_label="Use this code",
        accent_color="#f5f5f7",
    ),
    EmailTemplate(
        key="password_reset",
        name="Password reset OTP",
        subject="Reset your {{brand_name}} password",
        headline="Reset your password",
        body=(
            "Enter {{code}} to reset your dashboard password. "
            "Ignore this email if you did not request it."
        ),
        button_label="Reset password",
        accent_color="#f5f5f7",
    ),
)


@dataclass(frozen=True)
class DashboardSettings:
    app_domain: str = ""
    auth_domain: str = ""
    allowed_origins: tuple[str, ...] = ()
    redirect_urls: tuple[str, ...] = ()
    resend_from_email: str = ""
    resend_api_key: str | None = None
    google_client_id: str = ""
    google_client_secret: str | None = None
    brand_name: str = "Passport Auth"
    primary_color: str = "#f5f5f7"
    password_login_enabled: bool = True
    otp_login_enabled: bool = False
    magic_link_enabled: bool = False
    google_oauth_enabled: bool = False
    password_reset_otp_enabled: bool = True
    email_templates: tuple[EmailTemplate, ...] = DEFAULT_EMAIL_TEMPLATES


class SetupStore(Protocol):
    def get_owner(self) -> OwnerAccount | None: ...

    def get_owner_by_email(self, email: str) -> OwnerAccount | None: ...

    def create_owner(self, *, email: str, password: str) -> OwnerAccount: ...

    def update_owner_password(self, *, email: str, password: str) -> None: ...

    def create_password_reset_otp(self, *, email: str, otp: str, expires_at: int) -> None: ...

    def consume_password_reset_otp(self, *, email: str, otp: str, now: int) -> bool: ...

    def get_dashboard_settings(self) -> DashboardSettings: ...

    def save_dashboard_settings(self, settings: DashboardSettings) -> DashboardSettings: ...


class InMemorySetupStore:
    def __init__(self) -> None:
        self.owner: OwnerAccount | None = None
        self.password_reset_otps: dict[str, PasswordResetOtp] = {}
        self.dashboard_settings = DashboardSettings()

    def get_owner(self) -> OwnerAccount | None:
        return self.owner

    def get_owner_by_email(self, email: str) -> OwnerAccount | None:
        if self.owner and self.owner.email == email:
            return self.owner
        return None

    def create_owner(self, *, email: str, password: str) -> OwnerAccount:
        if self.owner:
            raise SetupAlreadyCompleteError

        self.owner = OwnerAccount(email=email, password_hash=hash_password(password), role="owner")
        return self.owner

    def update_owner_password(self, *, email: str, password: str) -> None:
        if not self.owner or self.owner.email != email:
            return

        self.owner = OwnerAccount(
            email=self.owner.email,
            password_hash=hash_password(password),
            role=self.owner.role,
        )

    def create_password_reset_otp(self, *, email: str, otp: str, expires_at: int) -> None:
        self.password_reset_otps[email] = PasswordResetOtp(
            email=email,
            otp_hash=hash_password(otp),
            expires_at=expires_at,
        )

    def consume_password_reset_otp(self, *, email: str, otp: str, now: int) -> bool:
        reset_otp = self.password_reset_otps.get(email)
        if not reset_otp or reset_otp.expires_at < now:
            return False

        if not verify_password(otp, reset_otp.otp_hash):
            return False

        del self.password_reset_otps[email]
        return True

    def get_dashboard_settings(self) -> DashboardSettings:
        return self.dashboard_settings

    def save_dashboard_settings(self, settings: DashboardSettings) -> DashboardSettings:
        self.dashboard_settings = settings
        return settings


class PostgresSetupStore:
    def __init__(self, database_url: str, *, encryption_key: str) -> None:
        self.database_url = database_url
        self.encryption_key = encryption_key
        self._schema_lock = Lock()
        self._schema_ready = False

    def get_owner(self) -> OwnerAccount | None:
        self._ensure_schema()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT email, password_hash, role
                FROM app_users
                WHERE role = 'owner'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()

        if not row:
            return None

        return OwnerAccount(email=row[0], password_hash=row[1], role=row[2])

    def get_owner_by_email(self, email: str) -> OwnerAccount | None:
        self._ensure_schema()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT email, password_hash, role
                FROM app_users
                WHERE email = %s AND role = 'owner'
                LIMIT 1
                """,
                (email,),
            ).fetchone()

        if not row:
            return None

        return OwnerAccount(email=row[0], password_hash=row[1], role=row[2])

    def create_owner(self, *, email: str, password: str) -> OwnerAccount:
        self._ensure_schema()
        existing_owner = self.get_owner()
        if existing_owner:
            raise SetupAlreadyCompleteError

        owner = OwnerAccount(email=email, password_hash=hash_password(password), role="owner")
        user_id = str(uuid4())

        try:
            with self._connect() as conn:
                with conn.transaction():
                    conn.execute(
                        """
                        INSERT INTO app_users (id, email, password_hash, role)
                        VALUES (%s, %s, %s, 'owner')
                        """,
                        (user_id, owner.email, owner.password_hash),
                    )
        except Exception as exc:
            if "app_users_single_owner" in str(exc) or "app_users_email_key" in str(exc):
                raise SetupAlreadyCompleteError from exc
            raise

        return owner

    def update_owner_password(self, *, email: str, password: str) -> None:
        self._ensure_schema()

        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    UPDATE app_users
                    SET password_hash = %s
                    WHERE email = %s AND role = 'owner'
                    """,
                    (hash_password(password), email),
                )

    def create_password_reset_otp(self, *, email: str, otp: str, expires_at: int) -> None:
        self._ensure_schema()
        expires_at_datetime = datetime.fromtimestamp(expires_at, tz=UTC)

        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO password_reset_otps (id, email, otp_hash, expires_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (str(uuid4()), email, hash_password(otp), expires_at_datetime),
                )

    def consume_password_reset_otp(self, *, email: str, otp: str, now: int) -> bool:
        self._ensure_schema()
        now_datetime = datetime.fromtimestamp(now, tz=UTC)

        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT id, otp_hash
                    FROM password_reset_otps
                    WHERE email = %s
                      AND expires_at >= %s
                      AND consumed_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (email, now_datetime),
                ).fetchone()

                if not row or not verify_password(otp, row[1]):
                    return False

                conn.execute(
                    """
                    UPDATE password_reset_otps
                    SET consumed_at = now()
                    WHERE id = %s
                    """,
                    (row[0],),
                )
                return True

    def get_dashboard_settings(self) -> DashboardSettings:
        self._ensure_schema()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT value::text
                FROM app_settings
                WHERE key = 'dashboard'
                LIMIT 1
                """
            ).fetchone()

        if not row:
            return DashboardSettings()

        return dashboard_settings_from_storage_dict(
            json.loads(row[0]),
            encryption_key=self.encryption_key,
        )

    def save_dashboard_settings(self, settings: DashboardSettings) -> DashboardSettings:
        self._ensure_schema()
        settings_json = json.dumps(
            dashboard_settings_to_storage_dict(settings, encryption_key=self.encryption_key)
        )

        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES ('dashboard', %s::jsonb, now())
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value,
                        updated_at = now()
                    """,
                    (settings_json,),
                )

        return settings

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return

        with self._schema_lock:
            if self._schema_ready:
                return

            with self._connect() as conn:
                with conn.transaction():
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS app_users (
                            id UUID PRIMARY KEY,
                            email TEXT NOT NULL UNIQUE,
                            password_hash TEXT NOT NULL,
                            role TEXT NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE UNIQUE INDEX IF NOT EXISTS app_users_single_owner
                        ON app_users ((role))
                        WHERE role = 'owner'
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS password_reset_otps (
                            id UUID PRIMARY KEY,
                            email TEXT NOT NULL,
                            otp_hash TEXT NOT NULL,
                            expires_at TIMESTAMPTZ NOT NULL,
                            consumed_at TIMESTAMPTZ,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS password_reset_otps_email_created_at
                        ON password_reset_otps (email, created_at DESC)
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS app_settings (
                            key TEXT PRIMARY KEY,
                            value JSONB NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )

            self._schema_ready = True

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)


def create_setup_store(database_url: str | None, *, encryption_key: str) -> SetupStore:
    if database_url:
        return PostgresSetupStore(database_url, encryption_key=encryption_key)

    return InMemorySetupStore()


def dashboard_settings_to_dict(settings: DashboardSettings) -> dict[str, object]:
    data = asdict(settings)
    data["allowed_origins"] = list(settings.allowed_origins)
    data["redirect_urls"] = list(settings.redirect_urls)
    data["email_templates"] = [asdict(template) for template in settings.email_templates]
    return data


def dashboard_settings_from_dict(data: dict[str, object]) -> DashboardSettings:
    defaults = DashboardSettings()
    merged = dashboard_settings_to_dict(defaults)
    merged.update(data)
    return DashboardSettings(
        app_domain=str(merged["app_domain"]),
        auth_domain=str(merged["auth_domain"]),
        allowed_origins=_string_tuple(merged["allowed_origins"]),
        redirect_urls=_string_tuple(merged["redirect_urls"]),
        resend_from_email=str(merged["resend_from_email"]),
        resend_api_key=_optional_string(merged["resend_api_key"]),
        google_client_id=str(merged["google_client_id"]),
        google_client_secret=_optional_string(merged["google_client_secret"]),
        brand_name=str(merged["brand_name"]),
        primary_color=str(merged["primary_color"]),
        password_login_enabled=bool(merged["password_login_enabled"]),
        otp_login_enabled=bool(merged["otp_login_enabled"]),
        magic_link_enabled=bool(merged["magic_link_enabled"]),
        google_oauth_enabled=bool(merged["google_oauth_enabled"]),
        password_reset_otp_enabled=bool(merged["password_reset_otp_enabled"]),
        email_templates=_email_templates_tuple(merged["email_templates"]),
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()

    return tuple(str(item).strip() for item in value if str(item).strip())


def _optional_string(value: object) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()
    return cleaned or None


def _email_templates_tuple(value: object) -> tuple[EmailTemplate, ...]:
    if not isinstance(value, list | tuple):
        return DEFAULT_EMAIL_TEMPLATES

    templates: list[EmailTemplate] = []
    seen_keys: set[str] = set()
    defaults_by_key = {template.key: template for template in DEFAULT_EMAIL_TEMPLATES}

    for item in value:
        if not isinstance(item, dict):
            continue

        key = _clean_template_value(item.get("key"), "")
        if not key:
            continue

        fallback = defaults_by_key.get(
            key,
            EmailTemplate(
                key=key,
                name=key.replace("_", " ").title(),
                subject="",
                headline="",
                body="",
                button_label="",
                accent_color="#f5f5f7",
            ),
        )
        templates.append(
            EmailTemplate(
                key=key,
                name=_clean_template_value(item.get("name"), fallback.name),
                subject=_clean_template_value(item.get("subject"), fallback.subject),
                headline=_clean_template_value(item.get("headline"), fallback.headline),
                body=_clean_template_value(item.get("body"), fallback.body),
                button_label=_clean_template_value(
                    item.get("button_label"),
                    fallback.button_label,
                ),
                accent_color=_clean_template_value(
                    item.get("accent_color"),
                    fallback.accent_color,
                ),
            )
        )
        seen_keys.add(key)

    for template in DEFAULT_EMAIL_TEMPLATES:
        if template.key not in seen_keys:
            templates.append(template)

    return tuple(templates) or DEFAULT_EMAIL_TEMPLATES


def _clean_template_value(value: object, default: str) -> str:
    if value is None:
        return default

    cleaned = str(value).strip()
    return cleaned or default


def dashboard_settings_to_storage_dict(
    settings: DashboardSettings,
    *,
    encryption_key: str,
) -> dict[str, object]:
    data = dashboard_settings_to_dict(settings)
    data["resend_api_key"] = encrypt_secret(settings.resend_api_key, encryption_key=encryption_key)
    data["google_client_secret"] = encrypt_secret(
        settings.google_client_secret,
        encryption_key=encryption_key,
    )
    return data


def dashboard_settings_from_storage_dict(
    data: dict[str, object],
    *,
    encryption_key: str,
) -> DashboardSettings:
    decrypted = data.copy()
    decrypted["resend_api_key"] = decrypt_secret(
        _optional_string(decrypted.get("resend_api_key")),
        encryption_key=encryption_key,
    )
    decrypted["google_client_secret"] = decrypt_secret(
        _optional_string(decrypted.get("google_client_secret")),
        encryption_key=encryption_key,
    )
    return dashboard_settings_from_dict(decrypted)
