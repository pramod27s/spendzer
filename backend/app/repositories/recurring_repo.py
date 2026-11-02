import uuid
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RecurringGroup, Transaction
from app.models.enums import RecurringStatus


async def list_for_user(session: AsyncSession, user_id: uuid.UUID) -> Sequence[RecurringGroup]:
    stmt = (
        select(RecurringGroup)
        .where(RecurringGroup.user_id == user_id)
        .order_by(RecurringGroup.typical_amount.desc())
    )
    return (await session.scalars(stmt)).all()


async def get(
    session: AsyncSession, user_id: uuid.UUID, group_id: uuid.UUID
) -> RecurringGroup | None:
    return await session.scalar(
        select(RecurringGroup).where(
            RecurringGroup.id == group_id, RecurringGroup.user_id == user_id
        )
    )


async def active_for_plan(session: AsyncSession, user_id: uuid.UUID) -> Sequence[RecurringGroup]:
    """Active groups the user hasn't dismissed: these become a plan's fixed costs."""
    stmt = select(RecurringGroup).where(
        RecurringGroup.user_id == user_id,
        RecurringGroup.active.is_(True),
        RecurringGroup.status != RecurringStatus.DISMISSED,
    )
    return (await session.scalars(stmt)).all()


async def clear_transaction_links(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(Transaction)
        .where(Transaction.user_id == user_id, Transaction.is_recurring.is_(True))
        .values(is_recurring=False, recurring_group_id=None)
    )


async def link_transactions(
    session: AsyncSession, user_id: uuid.UUID, group_id: uuid.UUID, txn_ids: Sequence[uuid.UUID]
) -> None:
    if not txn_ids:
        return
    await session.execute(
        update(Transaction)
        .where(Transaction.user_id == user_id, Transaction.id.in_(txn_ids))
        .values(is_recurring=True, recurring_group_id=group_id)
    )


async def clear_group_links(session: AsyncSession, user_id: uuid.UUID, group_id: uuid.UUID) -> None:
    await session.execute(
        update(Transaction)
        .where(Transaction.user_id == user_id, Transaction.recurring_group_id == group_id)
        .values(is_recurring=False, recurring_group_id=None)
    )
