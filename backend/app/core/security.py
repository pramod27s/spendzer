import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


@dataclass(frozen=True)
class IssuedToken:
    token: str
    jti: uuid.UUID
    expires_at: datetime


def _issue(user_id: uuid.UUID, token_type: TokenType, ttl: timedelta) -> IssuedToken:
    settings = get_settings()
    now = datetime.now(UTC)
    jti = uuid.uuid4()
    expires_at = now + ttl
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": str(jti),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return IssuedToken(token=token, jti=jti, expires_at=expires_at)


def create_access_token(user_id: uuid.UUID) -> IssuedToken:
    return _issue(user_id, "access", timedelta(minutes=get_settings().access_token_minutes))


def create_refresh_token(user_id: uuid.UUID) -> IssuedToken:
    return _issue(user_id, "refresh", timedelta(days=get_settings().refresh_token_days))


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    jti: uuid.UUID


def decode_token(token: str, expected_type: TokenType) -> TokenClaims | None:
    """Return claims for a valid token of the expected type, else None."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != expected_type:
            return None
        return TokenClaims(user_id=uuid.UUID(payload["sub"]), jti=uuid.UUID(payload["jti"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
