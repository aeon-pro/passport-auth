import hmac
import time
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from passport_auth.dashboard.tokens import (
    InvalidTokenError,
    _base64url_encode,
    _base64url_json,
    _decode_json,
)


def create_public_access_token(
    *,
    user_id: str,
    email: str,
    role: str,
    private_key_pem: str,
    issuer: str,
    audience: str,
    ttl_seconds: int,
) -> str:
    now = int(time.time())
    header = {
        "alg": "RS256",
        "typ": "JWT",
        "kid": public_key_id(private_key_pem),
    }
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + ttl_seconds,
    }
    encoded_header = _base64url_json(header)
    encoded_payload = _base64url_json(payload)
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = _sign_rs256(signing_input, private_key_pem)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_public_access_token(
    token: str,
    *,
    public_key_pem: str,
    issuer: str,
    audience: str,
) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
    except ValueError as exc:
        raise InvalidTokenError from exc

    header = _decode_json(encoded_header)
    if header.get("alg") != "RS256" or not header.get("kid"):
        raise InvalidTokenError

    _verify_rs256(
        f"{encoded_header}.{encoded_payload}",
        encoded_signature,
        public_key_pem,
    )

    payload = _decode_json(encoded_payload)
    if int(payload.get("exp", 0)) < int(time.time()):
        raise InvalidTokenError

    if payload.get("type") != "access" or not payload.get("sub") or not payload.get("email"):
        raise InvalidTokenError
    if payload.get("iss") != issuer or payload.get("aud") != audience:
        raise InvalidTokenError
    if not isinstance(payload.get("iat"), int):
        raise InvalidTokenError

    return payload


def generate_public_token_private_key_pem() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def public_key_pem(private_key_pem: str) -> str:
    public_key = _load_private_key(private_key_pem).public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def public_key_id(private_key_pem: str) -> str:
    public_key = _load_private_key(private_key_pem).public_key()
    public_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return _base64url_encode(hmac.digest(b"passport-auth-kid", public_der, "sha256"))[:32]


def public_jwks(private_key_pem: str) -> dict[str, list[dict[str, str]]]:
    public_key = _load_private_key(private_key_pem).public_key()
    numbers = public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "kid": public_key_id(private_key_pem),
                "alg": "RS256",
                "n": _base64url_uint(numbers.n),
                "e": _base64url_uint(numbers.e),
            }
        ]
    }


def _sign_rs256(data: str, private_key_pem: str) -> str:
    signature = _load_private_key(private_key_pem).sign(
        data.encode("ascii"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return _base64url_encode(signature)


def _verify_rs256(data: str, encoded_signature: str, public_key_pem_value: str) -> None:
    try:
        signature = _base64url_decode(encoded_signature)
        public_key = _load_public_key(public_key_pem_value)
        public_key.verify(
            signature,
            data.encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise InvalidTokenError from exc


def _load_private_key(private_key_pem: str) -> RSAPrivateKey:
    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=None,
        )
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError from exc

    if not isinstance(private_key, RSAPrivateKey):
        raise InvalidTokenError
    return private_key


def _load_public_key(public_key_pem_value: str) -> RSAPublicKey:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem_value.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError from exc

    if not isinstance(public_key, RSAPublicKey):
        raise InvalidTokenError
    return public_key


def _base64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return _base64url_encode(value.to_bytes(length, "big"))


def _base64url_decode(data: str) -> bytes:
    import base64

    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))
