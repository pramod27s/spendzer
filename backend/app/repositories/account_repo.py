import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account
from app.models.enums import AccountType


async def list_for_user(session: AsyncSession, user_id: uuid.UUID) -> Sequence[Account]:
    stmt = select(Account).where(Account.user_id == user_id).order_by(Account.created_at)
    return (await session.scalars(stmt)).all()


async def get(session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID) -> Account | None:
    return await session.scalar(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )


async def create(session: AsyncSession, user_id: uuid.UUID, **fields: object) -> Account:
    account = Account(user_id=user_id, **fields)
    session.add(account)
    await session.flush()
    return account


async def get_or_create_cash(session: AsyncSession, user_id: uuid.UUID) -> Account:
    existing = await session.scalar(
        select(Account)
        .where(Account.user_id == user_id, Account.type == AccountType.CASH)
        .order_by(Account.created_at)
        .limit(1)
    )
    if existing:
        return existing
    return await create(session, user_id, name="Cash", type=AccountType.CASH)


async def delete(session: AsyncSession, account: Account) -> None:
    await session.delete(account)
