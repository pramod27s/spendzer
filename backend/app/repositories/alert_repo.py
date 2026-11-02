import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, *, unread_only: bool, limit: int
) -> Sequence[Alert]:
    stmt = select(Alert).where(Alert.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Alert.read.is_(False))
    stmt = stmt.order_by(Alert.created_at.desc()).limit(limit)
    return (await session.scalars(stmt)).all()


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count(Alert.id)).where(Alert.user_id == user_id, Alert.read.is_(False))
        )
        or 0
    )


async def get(session: AsyncSession, user_id: uuid.UUID, alert_id: uuid.UUID) -> Alert | None:
    return await session.scalar(select(Alert).where(Alert.id == alert_id, Alert.user_id == user_id))


async def existing_keys(
    session: AsyncSession, user_id: uuid.UUID, month: date
) -> set[tuple[str, uuid.UUID | None]]:
    """(type, category_id) already alerted for the month — alerts never repeat."""
    stmt = select(Alert.type, Alert.category_id).where(
        Alert.user_id == user_id, Alert.month == month
    )
    return {(t, c) for t, c in (await session.execute(stmt)).all()}


async def add_many(session: AsyncSession, alerts: Sequence[Alert]) -> None:
    session.add_all(alerts)
    await session.flush()


async def mark_all_read(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(Alert).where(Alert.user_id == user_id, Alert.read.is_(False)).values(read=True)
    )
