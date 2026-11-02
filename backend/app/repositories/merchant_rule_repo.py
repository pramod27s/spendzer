import uuid
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, MerchantRule
from app.models.enums import Bucket, MatchType


async def list_with_buckets(
    session: AsyncSession, user_id: uuid.UUID
) -> Sequence[tuple[MerchantRule, Bucket]]:
    """User + global rules, each with its category's bucket (the categorizer needs both)."""
    stmt = (
        select(MerchantRule, Category.bucket)
        .join(Category, Category.id == MerchantRule.category_id)
        .where(or_(MerchantRule.user_id.is_(None), MerchantRule.user_id == user_id))
    )
    return [(rule, bucket) for rule, bucket in (await session.execute(stmt)).all()]


async def list_user(session: AsyncSession, user_id: uuid.UUID) -> Sequence[MerchantRule]:
    stmt = (
        select(MerchantRule)
        .where(MerchantRule.user_id == user_id)
        .order_by(MerchantRule.created_at.desc())
    )
    return (await session.scalars(stmt)).all()


async def get_user(
    session: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID
) -> MerchantRule | None:
    return await session.scalar(
        select(MerchantRule).where(MerchantRule.id == rule_id, MerchantRule.user_id == user_id)
    )


async def create(session: AsyncSession, user_id: uuid.UUID, **fields: object) -> MerchantRule:
    rule = MerchantRule(user_id=user_id, **fields)
    session.add(rule)
    await session.flush()
    return rule


async def upsert_exact(
    session: AsyncSession, user_id: uuid.UUID, merchant: str, category_id: uuid.UUID
) -> MerchantRule:
    """One exact-match user rule per merchant; re-pointing it replaces the category."""
    existing = await session.scalar(
        select(MerchantRule).where(
            MerchantRule.user_id == user_id,
            MerchantRule.match_type == MatchType.EXACT,
            MerchantRule.pattern == merchant,
        )
    )
    if existing:
        existing.category_id = category_id
        await session.flush()
        return existing
    return await create(
        session,
        user_id,
        pattern=merchant,
        match_type=MatchType.EXACT,
        category_id=category_id,
        priority=0,
    )


async def delete(session: AsyncSession, rule: MerchantRule) -> None:
    await session.delete(rule)
