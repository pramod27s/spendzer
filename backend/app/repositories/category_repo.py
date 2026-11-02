import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, MerchantRule, Transaction


def _visible(user_id: uuid.UUID) -> ColumnElement[bool]:
    return or_(Category.user_id.is_(None), Category.user_id == user_id)


async def list_visible(session: AsyncSession, user_id: uuid.UUID) -> Sequence[Category]:
    stmt = select(Category).where(_visible(user_id)).order_by(Category.bucket, Category.name)
    return (await session.scalars(stmt)).all()


async def get_visible(
    session: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
) -> Category | None:
    return await session.scalar(
        select(Category).where(Category.id == category_id, _visible(user_id))
    )


async def get_owned(
    session: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
) -> Category | None:
    return await session.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )


async def get_system_by_name(session: AsyncSession, name: str) -> Category | None:
    return await session.scalar(
        select(Category).where(Category.user_id.is_(None), Category.name == name)
    )


async def create(session: AsyncSession, user_id: uuid.UUID, **fields: object) -> Category:
    category = Category(user_id=user_id, **fields)
    session.add(category)
    await session.flush()
    return category


async def delete_reassigning(
    session: AsyncSession, user_id: uuid.UUID, category: Category, fallback_id: uuid.UUID
) -> None:
    """Move the user's transactions to `fallback_id`, drop their rules, then delete."""
    await session.execute(
        update(Transaction)
        .where(Transaction.user_id == user_id, Transaction.category_id == category.id)
        .values(category_id=fallback_id)
    )
    await session.execute(
        delete(MerchantRule).where(
            MerchantRule.user_id == user_id, MerchantRule.category_id == category.id
        )
    )
    await session.delete(category)
