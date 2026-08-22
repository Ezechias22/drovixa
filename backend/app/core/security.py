from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hasher = PasswordHash.recommended()


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: UUID
    session_id: UUID
    token_id: UUID


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(*, user_id: UUID, session_id: UUID) -> tuple[str, int]:
    settings = get_settings()
    issued_at = utcnow()
    expires_at = issued_at + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": str(uuid4()),
        "typ": "access",
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    encoded = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    token = encoded.decode() if isinstance(encoded, bytes) else encoded
    return token, int((expires_at - issued_at).total_seconds())


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        options={"require": ["sub", "sid", "jti", "typ", "iat", "nbf", "exp"]},
    )
    if not hmac.compare_digest(str(payload.get("typ", "")), "access"):
        raise jwt.InvalidTokenError("Unexpected token type")
    return AccessTokenClaims(
        user_id=UUID(payload["sub"]),
        session_id=UUID(payload["sid"]),
        token_id=UUID(payload["jti"]),
    )


def create_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(64)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw_token: str) -> str:
    secret = get_settings().REFRESH_SECRET.encode()
    return hmac.new(secret, raw_token.encode(), hashlib.sha256).hexdigest()
