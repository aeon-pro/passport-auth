import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

from passport_auth.setup.passwords import hash_password, verify_password


class AuthUserAlreadyExistsError(Exception):
    """Raised when a public auth user email is already registered."""


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    name: str = ""
    password_hash: str | None = None
    role: str = "user"
    is_active: bool = True
    email_verified: bool = True
    user_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class AuthCode:
    user_id: str
    redirect_url: str
    code_challenge: str
    expires_at: int


@dataclass(frozen=True)
class MagicLink:
    email: str
    redirect_url: str
    code_challenge: str
    expires_at: int


@dataclass(frozen=True)
class RefreshToken:
    user_id: str
    expires_at: int


@dataclass(frozen=True)
class OAuthState:
    redirect_url: str
    code_challenge: str
    expires_at: int


@dataclass(frozen=True)
class PendingRegistration:
    email: str
    name: str
    password_hash: str
    redirect_url: str
    code_challenge: str
    expires_at: int


class AuthStore(Protocol):
    def create_user(
        self,
        *,
        email: str,
        name: str | None = None,
        password: str | None = None,
        password_hash: str | None = None,
        email_verified: bool = True,
        user_metadata: dict[str, Any] | None = None,
    ) -> AuthUser: ...

    def get_user_by_email(self, email: str) -> AuthUser | None: ...

    def get_user_by_id(self, user_id: str) -> AuthUser | None: ...

    def list_users(
        self,
        *,
        query: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuthUser], int]: ...

    def update_user_password(self, *, email: str, password: str) -> None: ...

    def update_user_profile(
        self,
        *,
        email: str,
        name: str | None = None,
        email_verified: bool | None = None,
    ) -> AuthUser | None: ...

    def update_user(
        self,
        *,
        user_id: str,
        email: str | None = None,
        name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        email_verified: bool | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> AuthUser | None: ...

    def create_pending_registration(
        self,
        *,
        email: str,
        name: str,
        password: str,
        redirect_url: str,
        code_challenge: str,
        otp: str,
        expires_at: int,
    ) -> None: ...

    def consume_pending_registration(
        self,
        *,
        email: str,
        otp: str,
        now: int,
    ) -> PendingRegistration | None: ...

    def create_auth_code(
        self,
        *,
        code: str,
        user_id: str,
        redirect_url: str,
        code_challenge: str,
        expires_at: int,
    ) -> None: ...

    def consume_auth_code(self, *, code: str, now: int) -> AuthCode | None: ...

    def create_refresh_token(self, *, token: str, user_id: str, expires_at: int) -> None: ...

    def consume_refresh_token(self, *, token: str, now: int) -> RefreshToken | None: ...

    def revoke_refresh_token(self, *, token: str) -> bool: ...

    def create_otp(self, *, email: str, otp: str, purpose: str, expires_at: int) -> None: ...

    def consume_otp(self, *, email: str, otp: str, purpose: str, now: int) -> bool: ...

    def create_magic_link(
        self,
        *,
        token: str,
        email: str,
        redirect_url: str,
        code_challenge: str,
        expires_at: int,
    ) -> None: ...

    def consume_magic_link(self, *, token: str, now: int) -> MagicLink | None: ...

    def create_oauth_state(
        self,
        *,
        state: str,
        redirect_url: str,
        code_challenge: str,
        expires_at: int,
    ) -> None: ...

    def consume_oauth_state(self, *, state: str, now: int) -> OAuthState | None: ...


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_user_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return dict(value)


class InMemoryAuthStore:
    def __init__(self) -> None:
        self.users_by_id: dict[str, AuthUser] = {}
        self.users_by_email: dict[str, AuthUser] = {}
        self.auth_codes: dict[str, AuthCode] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self.otps: dict[tuple[str, str], tuple[str, int]] = {}
        self.pending_registrations: dict[str, tuple[PendingRegistration, str]] = {}
        self.magic_links: dict[str, MagicLink] = {}
        self.oauth_states: dict[str, OAuthState] = {}

    def create_user(
        self,
        *,
        email: str,
        name: str | None = None,
        password: str | None = None,
        password_hash: str | None = None,
        email_verified: bool = True,
        user_metadata: dict[str, Any] | None = None,
    ) -> AuthUser:
        normalized_email = email.strip().lower()
        if normalized_email in self.users_by_email:
            raise AuthUserAlreadyExistsError

        user = AuthUser(
            id=str(uuid4()),
            email=normalized_email,
            name=name or "",
            password_hash=password_hash or (hash_password(password) if password else None),
            email_verified=email_verified,
            user_metadata=normalize_user_metadata(user_metadata),
        )
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user
        return user

    def get_user_by_email(self, email: str) -> AuthUser | None:
        return self.users_by_email.get(email.strip().lower())

    def get_user_by_id(self, user_id: str) -> AuthUser | None:
        return self.users_by_id.get(user_id)

    def list_users(
        self,
        *,
        query: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuthUser], int]:
        normalized_query = query.strip().lower()
        users = list(self.users_by_id.values())
        if normalized_query:
            users = [
                user
                for user in users
                if normalized_query in user.email.lower()
                or normalized_query in user.name.lower()
                or normalized_query in user.role.lower()
            ]

        users.sort(key=lambda user: user.email)
        return users[offset : offset + limit], len(users)

    def update_user_password(self, *, email: str, password: str) -> None:
        user = self.get_user_by_email(email)
        if not user:
            return

        updated = AuthUser(
            id=user.id,
            email=user.email,
            name=user.name,
            password_hash=hash_password(password),
            role=user.role,
            is_active=user.is_active,
            email_verified=user.email_verified,
            user_metadata=normalize_user_metadata(user.user_metadata),
        )
        self.users_by_id[user.id] = updated
        self.users_by_email[user.email] = updated

    def update_user_profile(
        self,
        *,
        email: str,
        name: str | None = None,
        email_verified: bool | None = None,
    ) -> AuthUser | None:
        user = self.get_user_by_email(email)
        if not user:
            return None

        updated = AuthUser(
            id=user.id,
            email=user.email,
            name=name if name is not None else user.name,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
            email_verified=email_verified if email_verified is not None else user.email_verified,
            user_metadata=normalize_user_metadata(user.user_metadata),
        )
        self.users_by_id[user.id] = updated
        self.users_by_email[user.email] = updated
        return updated

    def update_user(
        self,
        *,
        user_id: str,
        email: str | None = None,
        name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        email_verified: bool | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> AuthUser | None:
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        normalized_email = email.strip().lower() if email is not None else user.email
        existing = self.users_by_email.get(normalized_email)
        if existing and existing.id != user.id:
            raise AuthUserAlreadyExistsError

        updated = AuthUser(
            id=user.id,
            email=normalized_email,
            name=name if name is not None else user.name,
            password_hash=user.password_hash,
            role=role if role is not None else user.role,
            is_active=is_active if is_active is not None else user.is_active,
            email_verified=email_verified if email_verified is not None else user.email_verified,
            user_metadata=(
                normalize_user_metadata(user_metadata)
                if user_metadata is not None
                else normalize_user_metadata(user.user_metadata)
            ),
        )
        if updated.email != user.email:
            del self.users_by_email[user.email]
        self.users_by_id[user.id] = updated
        self.users_by_email[updated.email] = updated
        return updated

    def create_pending_registration(
        self,
        *,
        email: str,
        name: str,
        password: str,
        redirect_url: str,
        code_challenge: str,
        otp: str,
        expires_at: int,
    ) -> None:
        normalized_email = email.strip().lower()
        self.pending_registrations[normalized_email] = (
            PendingRegistration(
                email=normalized_email,
                name=name,
                password_hash=hash_password(password),
                redirect_url=redirect_url,
                code_challenge=code_challenge,
                expires_at=expires_at,
            ),
            hash_password(otp),
        )

    def consume_pending_registration(
        self,
        *,
        email: str,
        otp: str,
        now: int,
    ) -> PendingRegistration | None:
        normalized_email = email.strip().lower()
        stored = self.pending_registrations.get(normalized_email)
        if not stored:
            return None

        pending_registration, otp_hash = stored
        if pending_registration.expires_at < now or not verify_password(otp, otp_hash):
            return None

        del self.pending_registrations[normalized_email]
        return pending_registration

    def create_auth_code(
        self,
        *,
        code: str,
        user_id: str,
        redirect_url: str,
        code_challenge: str,
        expires_at: int,
    ) -> None:
        self.auth_codes[hash_token(code)] = AuthCode(
            user_id=user_id,
            redirect_url=redirect_url,
            code_challenge=code_challenge,
            expires_at=expires_at,
        )

    def consume_auth_code(self, *, code: str, now: int) -> AuthCode | None:
        auth_code = self.auth_codes.pop(hash_token(code), None)
        if not auth_code or auth_code.expires_at < now:
            return None
        return auth_code

    def create_refresh_token(self, *, token: str, user_id: str, expires_at: int) -> None:
        self.refresh_tokens[hash_token(token)] = RefreshToken(
            user_id=user_id,
            expires_at=expires_at,
        )

    def consume_refresh_token(self, *, token: str, now: int) -> RefreshToken | None:
        refresh_token = self.refresh_tokens.pop(hash_token(token), None)
        if not refresh_token or refresh_token.expires_at < now:
            return None
        return refresh_token

    def revoke_refresh_token(self, *, token: str) -> bool:
        return self.refresh_tokens.pop(hash_token(token), None) is not None

    def create_otp(self, *, email: str, otp: str, purpose: str, expires_at: int) -> None:
        self.otps[(email.strip().lower(), purpose)] = (hash_password(otp), expires_at)

    def consume_otp(self, *, email: str, otp: str, purpose: str, now: int) -> bool:
        key = (email.strip().lower(), purpose)
        stored = self.otps.get(key)
        if not stored:
            return False
        otp_hash, expires_at = stored
        if expires_at < now or not verify_password(otp, otp_hash):
            return False
        del self.otps[key]
        return True

    def create_magic_link(
        self,
        *,
        token: str,
        email: str,
        redirect_url: str,
        code_challenge: str,
        expires_at: int,
    ) -> None:
        self.magic_links[hash_token(token)] = MagicLink(
            email=email.strip().lower(),
            redirect_url=redirect_url,
            code_challenge=code_challenge,
            expires_at=expires_at,
        )

    def consume_magic_link(self, *, token: str, now: int) -> MagicLink | None:
        magic_link = self.magic_links.pop(hash_token(token), None)
        if not magic_link or magic_link.expires_at < now:
            return None
        return magic_link

    def create_oauth_state(
        self,
        *,
        state: str,
        redirect_url: str,
        code_challenge: str,
        expires_at: int,
    ) -> None:
        self.oauth_states[hash_token(state)] = OAuthState(
            redirect_url=redirect_url,
            code_challenge=code_challenge,
            expires_at=expires_at,
        )

    def consume_oauth_state(self, *, state: str, now: int) -> OAuthState | None:
        oauth_state = self.oauth_states.pop(hash_token(state), None)
        if not oauth_state or oauth_state.expires_at < now:
            return None
        return oauth_state


class PostgresAuthStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._schema_lock = Lock()
        self._schema_ready = False

    def create_user(
        self,
        *,
        email: str,
        name: str | None = None,
        password: str | None = None,
        password_hash: str | None = None,
        email_verified: bool = True,
        user_metadata: dict[str, Any] | None = None,
    ) -> AuthUser:
        self._ensure_schema()
        user = AuthUser(
            id=str(uuid4()),
            email=email.strip().lower(),
            name=name or "",
            password_hash=password_hash or (hash_password(password) if password else None),
            email_verified=email_verified,
            user_metadata=normalize_user_metadata(user_metadata),
        )
        try:
            with self._connect() as conn:
                with conn.transaction():
                    from psycopg.types.json import Jsonb

                    conn.execute(
                        """
                        INSERT INTO auth_users
                            (
                                id,
                                email,
                                name,
                                password_hash,
                                role,
                                is_active,
                                email_verified,
                                user_metadata
                            )
                        VALUES (%s, %s, %s, %s, 'user', true, %s, %s)
                        """,
                        (
                            user.id,
                            user.email,
                            user.name,
                            user.password_hash,
                            user.email_verified,
                            Jsonb(user.user_metadata or {}),
                        ),
                    )
        except Exception as exc:
            if "auth_users_email_key" in str(exc):
                raise AuthUserAlreadyExistsError from exc
            raise
        return user

    def get_user_by_email(self, email: str) -> AuthUser | None:
        self._ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id::text,
                    email,
                    name,
                    password_hash,
                    role,
                    is_active,
                    email_verified,
                    user_metadata
                FROM auth_users
                WHERE email = %s
                LIMIT 1
                """,
                (email.strip().lower(),),
            ).fetchone()
        return _auth_user_from_row(row)

    def get_user_by_id(self, user_id: str) -> AuthUser | None:
        self._ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id::text,
                    email,
                    name,
                    password_hash,
                    role,
                    is_active,
                    email_verified,
                    user_metadata
                FROM auth_users
                WHERE id = %s
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return _auth_user_from_row(row)

    def list_users(
        self,
        *,
        query: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuthUser], int]:
        self._ensure_schema()
        normalized_query = query.strip()
        pattern = f"%{normalized_query}%"
        with self._connect() as conn:
            if normalized_query:
                rows = conn.execute(
                    """
                    SELECT
                        id::text,
                        email,
                        name,
                        password_hash,
                        role,
                        is_active,
                        email_verified,
                        user_metadata
                    FROM auth_users
                    WHERE email ILIKE %s OR name ILIKE %s OR role ILIKE %s
                    ORDER BY created_at DESC, email ASC
                    LIMIT %s OFFSET %s
                    """,
                    (pattern, pattern, pattern, limit, offset),
                ).fetchall()
                total_row = conn.execute(
                    """
                    SELECT count(*)
                    FROM auth_users
                    WHERE email ILIKE %s OR name ILIKE %s OR role ILIKE %s
                    """,
                    (pattern, pattern, pattern),
                ).fetchone()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        id::text,
                        email,
                        name,
                        password_hash,
                        role,
                        is_active,
                        email_verified,
                        user_metadata
                    FROM auth_users
                    ORDER BY created_at DESC, email ASC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                ).fetchall()
                total_row = conn.execute("SELECT count(*) FROM auth_users").fetchone()

        return [user for row in rows if (user := _auth_user_from_row(row))], int(total_row[0])

    def update_user_password(self, *, email: str, password: str) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    UPDATE auth_users
                    SET password_hash = %s
                    WHERE email = %s
                    """,
                    (hash_password(password), email.strip().lower()),
                )

    def update_user_profile(
        self,
        *,
        email: str,
        name: str | None = None,
        email_verified: bool | None = None,
    ) -> AuthUser | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    UPDATE auth_users
                    SET name = COALESCE(%s, name),
                        email_verified = COALESCE(%s, email_verified)
                    WHERE email = %s
                    RETURNING
                        id::text,
                        email,
                        name,
                        password_hash,
                        role,
                        is_active,
                        email_verified,
                        user_metadata
                    """,
                    (name, email_verified, email.strip().lower()),
                ).fetchone()

        return _auth_user_from_row(row)

    def update_user(
        self,
        *,
        user_id: str,
        email: str | None = None,
        name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        email_verified: bool | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> AuthUser | None:
        self._ensure_schema()
        try:
            with self._connect() as conn:
                with conn.transaction():
                    from psycopg.types.json import Jsonb

                    row = conn.execute(
                        """
                        UPDATE auth_users
                        SET email = COALESCE(%s, email),
                            name = COALESCE(%s, name),
                            role = COALESCE(%s, role),
                            is_active = COALESCE(%s, is_active),
                            email_verified = COALESCE(%s, email_verified),
                            user_metadata = COALESCE(%s, user_metadata)
                        WHERE id = %s
                        RETURNING
                            id::text,
                            email,
                            name,
                            password_hash,
                            role,
                            is_active,
                            email_verified,
                            user_metadata
                        """,
                        (
                            email.strip().lower() if email is not None else None,
                            name,
                            role,
                            is_active,
                            email_verified,
                            Jsonb(user_metadata) if user_metadata is not None else None,
                            user_id,
                        ),
                    ).fetchone()
        except Exception as exc:
            if "auth_users_email_key" in str(exc):
                raise AuthUserAlreadyExistsError from exc
            raise

        return _auth_user_from_row(row)

    def create_pending_registration(
        self,
        *,
        email: str,
        name: str,
        password: str,
        redirect_url: str,
        code_challenge: str,
        otp: str,
        expires_at: int,
    ) -> None:
        self._ensure_schema()
        expires_at_datetime = datetime.fromtimestamp(expires_at, tz=UTC)

        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO pending_registrations
                        (
                            email,
                            name,
                            password_hash,
                            redirect_url,
                            code_challenge,
                            otp_hash,
                            expires_at,
                            created_at
                        )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (email) DO UPDATE
                    SET name = EXCLUDED.name,
                        password_hash = EXCLUDED.password_hash,
                        redirect_url = EXCLUDED.redirect_url,
                        code_challenge = EXCLUDED.code_challenge,
                        otp_hash = EXCLUDED.otp_hash,
                        expires_at = EXCLUDED.expires_at,
                        created_at = now()
                    """,
                    (
                        email.strip().lower(),
                        name,
                        hash_password(password),
                        redirect_url,
                        code_challenge,
                        hash_password(otp),
                        expires_at_datetime,
                    ),
                )

    def consume_pending_registration(
        self,
        *,
        email: str,
        otp: str,
        now: int,
    ) -> PendingRegistration | None:
        self._ensure_schema()
        normalized_email = email.strip().lower()
        now_datetime = datetime.fromtimestamp(now, tz=UTC)

        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT
                        email,
                        name,
                        password_hash,
                        redirect_url,
                        code_challenge,
                        otp_hash,
                        expires_at
                    FROM pending_registrations
                    WHERE email = %s
                    LIMIT 1
                    """,
                    (normalized_email,),
                ).fetchone()

                if (
                    not row
                    or row[6] < now_datetime
                    or not verify_password(otp, row[5])
                ):
                    return None

                conn.execute(
                    """
                    DELETE FROM pending_registrations
                    WHERE email = %s
                    """,
                    (normalized_email,),
                )

        return PendingRegistration(
            email=row[0],
            name=row[1],
            password_hash=row[2],
            redirect_url=row[3],
            code_challenge=row[4],
            expires_at=int(row[6].timestamp()),
        )

    def create_auth_code(
        self,
        *,
        code: str,
        user_id: str,
        redirect_url: str,
        code_challenge: str,
        expires_at: int,
    ) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO auth_codes
                        (id, code_hash, user_id, redirect_url, code_challenge, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        hash_token(code),
                        user_id,
                        redirect_url,
                        code_challenge,
                        datetime.fromtimestamp(expires_at, tz=UTC),
                    ),
                )

    def consume_auth_code(self, *, code: str, now: int) -> AuthCode | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT id, user_id::text, redirect_url, code_challenge, expires_at
                    FROM auth_codes
                    WHERE code_hash = %s AND consumed_at IS NULL
                    LIMIT 1
                    """,
                    (hash_token(code),),
                ).fetchone()
                if not row or int(row[4].timestamp()) < now:
                    return None
                conn.execute("UPDATE auth_codes SET consumed_at = now() WHERE id = %s", (row[0],))
        return AuthCode(
            user_id=row[1],
            redirect_url=row[2],
            code_challenge=row[3],
            expires_at=int(row[4].timestamp()),
        )

    def create_refresh_token(self, *, token: str, user_id: str, expires_at: int) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO refresh_tokens (id, token_hash, user_id, expires_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        hash_token(token),
                        user_id,
                        datetime.fromtimestamp(expires_at, tz=UTC),
                    ),
                )

    def consume_refresh_token(self, *, token: str, now: int) -> RefreshToken | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT id, user_id::text, expires_at
                    FROM refresh_tokens
                    WHERE token_hash = %s AND revoked_at IS NULL
                    LIMIT 1
                    """,
                    (hash_token(token),),
                ).fetchone()
                if not row or int(row[2].timestamp()) < now:
                    return None
                conn.execute(
                    "UPDATE refresh_tokens SET revoked_at = now() WHERE id = %s",
                    (row[0],),
                )
        return RefreshToken(user_id=row[1], expires_at=int(row[2].timestamp()))

    def revoke_refresh_token(self, *, token: str) -> bool:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                result = conn.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked_at = now()
                    WHERE token_hash = %s AND revoked_at IS NULL
                    """,
                    (hash_token(token),),
                )
        return result.rowcount > 0

    def create_otp(self, *, email: str, otp: str, purpose: str, expires_at: int) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO auth_otps (id, email, otp_hash, purpose, expires_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        email.strip().lower(),
                        hash_password(otp),
                        purpose,
                        datetime.fromtimestamp(expires_at, tz=UTC),
                    ),
                )

    def consume_otp(self, *, email: str, otp: str, purpose: str, now: int) -> bool:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT id, otp_hash, expires_at
                    FROM auth_otps
                    WHERE email = %s
                      AND purpose = %s
                      AND consumed_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (email.strip().lower(), purpose),
                ).fetchone()
                if not row or int(row[2].timestamp()) < now or not verify_password(otp, row[1]):
                    return False
                conn.execute("UPDATE auth_otps SET consumed_at = now() WHERE id = %s", (row[0],))
        return True

    def create_magic_link(
        self,
        *,
        token: str,
        email: str,
        redirect_url: str,
        code_challenge: str,
        expires_at: int,
    ) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO magic_links
                        (id, token_hash, email, redirect_url, code_challenge, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        hash_token(token),
                        email.strip().lower(),
                        redirect_url,
                        code_challenge,
                        datetime.fromtimestamp(expires_at, tz=UTC),
                    ),
                )

    def consume_magic_link(self, *, token: str, now: int) -> MagicLink | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT id, email, redirect_url, code_challenge, expires_at
                    FROM magic_links
                    WHERE token_hash = %s AND consumed_at IS NULL
                    LIMIT 1
                    """,
                    (hash_token(token),),
                ).fetchone()
                if not row or int(row[4].timestamp()) < now:
                    return None
                conn.execute("UPDATE magic_links SET consumed_at = now() WHERE id = %s", (row[0],))
        return MagicLink(
            email=row[1],
            redirect_url=row[2],
            code_challenge=row[3],
            expires_at=int(row[4].timestamp()),
        )

    def create_oauth_state(
        self,
        *,
        state: str,
        redirect_url: str,
        code_challenge: str,
        expires_at: int,
    ) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO oauth_states
                        (id, state_hash, redirect_url, code_challenge, expires_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        hash_token(state),
                        redirect_url,
                        code_challenge,
                        datetime.fromtimestamp(expires_at, tz=UTC),
                    ),
                )

    def consume_oauth_state(self, *, state: str, now: int) -> OAuthState | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT id, redirect_url, code_challenge, expires_at
                    FROM oauth_states
                    WHERE state_hash = %s AND consumed_at IS NULL
                    LIMIT 1
                    """,
                    (hash_token(state),),
                ).fetchone()
                if not row or int(row[3].timestamp()) < now:
                    return None
                conn.execute("UPDATE oauth_states SET consumed_at = now() WHERE id = %s", (row[0],))
        return OAuthState(
            redirect_url=row[1],
            code_challenge=row[2],
            expires_at=int(row[3].timestamp()),
        )

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
                        CREATE TABLE IF NOT EXISTS auth_users (
                            id UUID PRIMARY KEY,
                            email TEXT NOT NULL UNIQUE,
                            name TEXT NOT NULL DEFAULT '',
                            password_hash TEXT,
                            role TEXT NOT NULL DEFAULT 'user',
                            is_active BOOLEAN NOT NULL DEFAULT true,
                            email_verified BOOLEAN NOT NULL DEFAULT true,
                            user_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                    conn.execute(
                        """
                        ALTER TABLE auth_users
                        ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT ''
                        """
                    )
                    conn.execute(
                        """
                        ALTER TABLE auth_users
                        ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT true
                        """
                    )
                    conn.execute(
                        """
                        ALTER TABLE auth_users
                        ADD COLUMN IF NOT EXISTS user_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS pending_registrations (
                            email TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            password_hash TEXT NOT NULL,
                            redirect_url TEXT NOT NULL,
                            code_challenge TEXT NOT NULL,
                            otp_hash TEXT NOT NULL,
                            expires_at TIMESTAMPTZ NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS auth_codes (
                            id UUID PRIMARY KEY,
                            code_hash TEXT NOT NULL UNIQUE,
                            user_id UUID NOT NULL REFERENCES auth_users(id),
                            redirect_url TEXT NOT NULL,
                            code_challenge TEXT NOT NULL,
                            expires_at TIMESTAMPTZ NOT NULL,
                            consumed_at TIMESTAMPTZ,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS refresh_tokens (
                            id UUID PRIMARY KEY,
                            token_hash TEXT NOT NULL UNIQUE,
                            user_id UUID NOT NULL REFERENCES auth_users(id),
                            expires_at TIMESTAMPTZ NOT NULL,
                            revoked_at TIMESTAMPTZ,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS auth_otps (
                            id UUID PRIMARY KEY,
                            email TEXT NOT NULL,
                            otp_hash TEXT NOT NULL,
                            purpose TEXT NOT NULL,
                            expires_at TIMESTAMPTZ NOT NULL,
                            consumed_at TIMESTAMPTZ,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS magic_links (
                            id UUID PRIMARY KEY,
                            token_hash TEXT NOT NULL UNIQUE,
                            email TEXT NOT NULL,
                            redirect_url TEXT NOT NULL,
                            code_challenge TEXT NOT NULL,
                            expires_at TIMESTAMPTZ NOT NULL,
                            consumed_at TIMESTAMPTZ,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS oauth_states (
                            id UUID PRIMARY KEY,
                            state_hash TEXT NOT NULL UNIQUE,
                            redirect_url TEXT NOT NULL,
                            code_challenge TEXT NOT NULL,
                            expires_at TIMESTAMPTZ NOT NULL,
                            consumed_at TIMESTAMPTZ,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
            self._schema_ready = True

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)


def _auth_user_from_row(row) -> AuthUser | None:
    if not row:
        return None
    return AuthUser(
        id=row[0],
        email=row[1],
        name=row[2],
        password_hash=row[3],
        role=row[4],
        is_active=bool(row[5]),
        email_verified=bool(row[6]),
        user_metadata=normalize_user_metadata(row[7] if len(row) > 7 else None),
    )


def create_auth_store(database_url: str | None) -> AuthStore:
    if database_url:
        return PostgresAuthStore(database_url)
    return InMemoryAuthStore()
