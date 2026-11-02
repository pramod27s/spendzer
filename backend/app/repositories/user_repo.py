import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken, User


async def get(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def create(session: AsyncSession, *, email: str, password_hash: str, name: str) -> User:
    user = User(email=email, password_hash=password_hash, name=name)
    session.add(user)
    await session.flush()
    return user


async def add_refresh_token(
    session: AsyncSession, *, user_id: uuid.UUID, jti: uuid.UUID, expires_at: datetime
) -> None:
    session.add(RefreshToken(user_id=user_id, jti=jti, expires_at=expires_at))
    await session.flush()


async def get_refresh_token(session: AsyncSession, jti: uuid.UUID) -> RefreshToken | None:
    return await session.scalar(select(RefreshToken).where(RefreshToken.jti == jti))


async def revoke_all_refresh_tokens(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
