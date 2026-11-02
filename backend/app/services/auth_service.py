from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError, ConflictError
from app.core.security import (
    IssuedToken,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.repositories import account_repo, user_repo
from app.schemas.auth import LoginIn, RegisterIn

# Verified against when the email is unknown, so response time doesn't reveal which emails exist.
_DUMMY_HASH = hash_password("spendzer-timing-equalizer")


@dataclass(frozen=True)
class Session:
    user: User
    access: IssuedToken
    refresh: IssuedToken


async def _issue(session: AsyncSession, user: User) -> Session:
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    await user_repo.add_refresh_token(
        session, user_id=user.id, jti=refresh.jti, expires_at=refresh.expires_at
    )
    await session.commit()
    return Session(user=user, access=access, refresh=refresh)


async def register(session: AsyncSession, data: RegisterIn) -> Session:
    if await user_repo.get_by_email(session, data.email):
        raise ConflictError("EMAIL_TAKEN", "An account with this email already exists.")
    user = await user_repo.create(
        session, email=data.email, password_hash=hash_password(data.password), name=data.name
    )
    await account_repo.get_or_create_cash(session, user.id)
    return await _issue(session, user)


async def login(session: AsyncSession, data: LoginIn) -> Session:
    user = await user_repo.get_by_email(session, data.email)
    if user is None:
        verify_password(data.password, _DUMMY_HASH)
        raise AuthError("INVALID_CREDENTIALS", "Email or password is incorrect.")
    if not verify_password(data.password, user.password_hash):
        raise AuthError("INVALID_CREDENTIALS", "Email or password is incorrect.")
    return await _issue(session, user)


async def refresh(session: AsyncSession, token: str | None) -> Session:
    """Rotate: the presented refresh token is revoked and a new pair issued.

    Presenting an already-revoked token means it leaked; every session for that user is ended.
    """
    claims = decode_token(token, "refresh") if token else None
    if claims is None:
        raise AuthError("REFRESH_INVALID", "Session expired. Please sign in again.")
    stored = await user_repo.get_refresh_token(session, claims.jti)
    if stored is None or stored.user_id != claims.user_id:
        raise AuthError("REFRESH_INVALID", "Session expired. Please sign in again.")
    if stored.revoked_at is not None:
        await user_repo.revoke_all_refresh_tokens(session, stored.user_id)
        await session.commit()
        raise AuthError("REFRESH_REUSED", "Session expired. Please sign in again.")
    user = await user_repo.get(session, claims.user_id)
    if user is None:
        raise AuthError("REFRESH_INVALID", "Session expired. Please sign in again.")
    stored.revoked_at = datetime.now(UTC)
    return await _issue(session, user)


async def logout(session: AsyncSession, token: str | None) -> None:
    claims = decode_token(token, "refresh") if token else None
    if claims is None:
        return
    stored = await user_repo.get_refresh_token(session, claims.jti)
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        await session.commit()
