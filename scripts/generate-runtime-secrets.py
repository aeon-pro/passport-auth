#!/usr/bin/env python3
from __future__ import annotations

import secrets
import stat
import string
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SECRET_LENGTH = 64
MIN_SECRET_LENGTH = 32
ALPHABET = string.ascii_letters + string.digits
SECRET_FILES = (
    "app_encryption_key",
    "dashboard_jwt_secret",
    "postgres_password",
    "clickhouse_password",
)
PRIVATE_KEY_FILES = ("public_jwt_private_key",)
SECRET_FILE_MODE = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
SECRET_DIR_MODE = (
    stat.S_IRUSR
    | stat.S_IWUSR
    | stat.S_IXUSR
    | stat.S_IRGRP
    | stat.S_IXGRP
    | stat.S_IROTH
    | stat.S_IXOTH
)


def random_secret() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(SECRET_LENGTH))


def private_key_pem() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def ensure_secret(path: Path) -> None:
    if path.exists() and path.read_text(encoding="utf-8").strip():
        value = path.read_text(encoding="utf-8").strip()
        if len(value) < MIN_SECRET_LENGTH:
            raise SystemExit(f"{path} exists but is shorter than {MIN_SECRET_LENGTH} characters.")
        path.chmod(SECRET_FILE_MODE)
        return

    path.write_text(random_secret() + "\n", encoding="utf-8")
    path.chmod(SECRET_FILE_MODE)


def ensure_private_key(path: Path) -> None:
    if path.exists() and path.read_text(encoding="utf-8").strip():
        value = path.read_text(encoding="utf-8").strip()
        if "-----BEGIN PRIVATE KEY-----" not in value:
            raise SystemExit(f"{path} exists but is not a PEM private key.")
        path.chmod(SECRET_FILE_MODE)
        return

    path.write_text(private_key_pem(), encoding="utf-8")
    path.chmod(SECRET_FILE_MODE)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate-runtime-secrets.py /path/to/secret-dir")

    secret_dir = Path(sys.argv[1])
    secret_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.chmod(SECRET_DIR_MODE)

    for filename in SECRET_FILES:
        ensure_secret(secret_dir / filename)
    for filename in PRIVATE_KEY_FILES:
        ensure_private_key(secret_dir / filename)


if __name__ == "__main__":
    main()
