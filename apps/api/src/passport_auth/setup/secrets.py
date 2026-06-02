import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def encrypt_secret(value: str | None, *, encryption_key: str) -> str | None:
    if not value:
        return None

    token = _fernet(encryption_key).encrypt(value.encode("utf-8")).decode("utf-8")
    return f"fernet:{token}"


def decrypt_secret(value: str | None, *, encryption_key: str) -> str | None:
    if not value:
        return None

    if not value.startswith("fernet:"):
        return value

    token = value.removeprefix("fernet:")
    try:
        return _fernet(encryption_key).decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None


def _fernet(encryption_key: str) -> Fernet:
    key_bytes = hashlib.sha256(encryption_key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)
