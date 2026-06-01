from dataclasses import dataclass
from threading import Lock
from typing import Protocol
from uuid import uuid4

from passport_auth.setup.passwords import hash_password


class SetupAlreadyCompleteError(Exception):
    """Raised when an owner account already exists."""


@dataclass(frozen=True)
class OwnerAccount:
    email: str
    password_hash: str
    role: str = "owner"


class SetupStore(Protocol):
    def get_owner(self) -> OwnerAccount | None: ...

    def get_owner_by_email(self, email: str) -> OwnerAccount | None: ...

    def create_owner(self, *, email: str, password: str) -> OwnerAccount: ...


class InMemorySetupStore:
    def __init__(self) -> None:
        self.owner: OwnerAccount | None = None

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


class PostgresSetupStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
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

            self._schema_ready = True

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)


def create_setup_store(database_url: str | None) -> SetupStore:
    if database_url:
        return PostgresSetupStore(database_url)

    return InMemorySetupStore()
