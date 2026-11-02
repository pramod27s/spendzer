import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Account, User
from app.repositories import account_repo
from app.schemas.account import AccountIn, AccountUpdate


async def list_accounts(session: AsyncSession, user: User) -> Sequence[Account]:
    return await account_repo.list_for_user(session, user.id)


async def get_account(session: AsyncSession, user: User, account_id: uuid.UUID) -> Account:
    account = await account_repo.get(session, user.id, account_id)
    if account is None:
        raise NotFoundError("Account")
    return account


async def create_account(session: AsyncSession, user: User, data: AccountIn) -> Account:
    account = await account_repo.create(session, user.id, **data.model_dump())
    await session.commit()
    return account


async def update_account(
    session: AsyncSession, user: User, account_id: uuid.UUID, data: AccountUpdate
) -> Account:
    account = await get_account(session, user, account_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    await session.commit()
    await session.refresh(account)
    return account


async def delete_account(session: AsyncSession, user: User, account_id: uuid.UUID) -> None:
    account = await get_account(session, user, account_id)
    await account_repo.delete(session, account)  # uploads + transactions cascade
    await session.commit()
