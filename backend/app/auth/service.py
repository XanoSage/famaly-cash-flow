from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

from app.core.config import settings

JWT_ALGORITHM = "HS256"
_password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = _password_hash.hash(secrets.token_urlsafe(24))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return _password_hash.verify(password, encoded_hash)
    except PwdlibError:
        return False


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: UUID, session_id: UUID) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "jti": str(uuid4()),
            "typ": "access",
            "iat": now,
            "exp": expires_at,
        },
        settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> tuple[UUID, UUID] | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "sid", "typ"]},
        )
        if payload.get("typ") != "access":
            return None
        return UUID(payload["sub"]), UUID(payload["sid"])
    except (InvalidTokenError, TypeError, ValueError, KeyError):
        return None


def access_token_expires_in() -> int:
    return settings.jwt_access_token_expire_minutes * 60
