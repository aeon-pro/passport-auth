import hmac
import time
from typing import Any

from passport_auth.dashboard.tokens import InvalidTokenError, _base64url_json, _decode_json, _sign


def create_public_access_token(
    *,
    user_id: str,
    email: str,
    role: str,
    secret: str,
    ttl_seconds: int,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "exp": int(time.time()) + ttl_seconds,
    }
    encoded_header = _base64url_json(header)
    encoded_payload = _base64url_json(payload)
    signature = _sign(f"{encoded_header}.{encoded_payload}", secret)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_public_access_token(token: str, *, secret: str) -> dict[str, Any]:
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

    if payload.get("type") != "access" or not payload.get("sub") or not payload.get("email"):
        raise InvalidTokenError

    return payload
