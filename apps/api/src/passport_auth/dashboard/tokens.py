import base64
import hashlib
import hmac
import json
import time
from typing import Any


class InvalidTokenError(Exception):
    """Raised when a dashboard JWT cannot be trusted."""


def create_dashboard_token(
    *,
    email: str,
    role: str,
    secret: str,
    ttl_seconds: int,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": email,
        "role": role,
        "exp": int(time.time()) + ttl_seconds,
    }
    encoded_header = _base64url_json(header)
    encoded_payload = _base64url_json(payload)
    signature = _sign(f"{encoded_header}.{encoded_payload}", secret)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_dashboard_token(token: str, *, secret: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
    except ValueError as exc:
        raise InvalidTokenError from exc

    expected_signature = _sign(f"{encoded_header}.{encoded_payload}", secret)
    if not hmac.compare_digest(encoded_signature, expected_signature):
        raise InvalidTokenError

    header = _decode_json(encoded_header)
    if header.get("alg") != "HS256":
        raise InvalidTokenError

    payload = _decode_json(encoded_payload)
    if int(payload.get("exp", 0)) < int(time.time()):
        raise InvalidTokenError

    if not payload.get("sub") or not payload.get("role"):
        raise InvalidTokenError

    return payload


def _base64url_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _base64url_encode(raw)


def _decode_json(data: str) -> dict[str, Any]:
    try:
        decoded = _base64url_decode(data)
        payload = json.loads(decoded)
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError from exc

    if not isinstance(payload, dict):
        raise InvalidTokenError

    return payload


def _sign(data: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), data.encode("ascii"), hashlib.sha256).digest()
    return _base64url_encode(digest)


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))
