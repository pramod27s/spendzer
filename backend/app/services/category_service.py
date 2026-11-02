import re
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.models import Category, MerchantRule, User
from app.models.enums import MatchType
from app.repositories import category_repo, merchant_rule_repo
from app.schemas.category import CategoryIn, CategoryUpdate, MerchantRuleIn


async def list_categories(session: AsyncSession, user: User) -> Sequence[Category]:
    return await category_repo.list_visible(session, user.id)


async def require_visible(session: AsyncSession, user: User, category_id: uuid.UUID) -> Category:
    category = await category_repo.get_visible(session, user.id, category_id)
    if category is None:
        raise NotFoundError("Category")
    return category


async def create_category(session: AsyncSession, user: User, data: CategoryIn) -> Category:
    category = await category_repo.create(session, user.id, **data.model_dump())
    await session.commit()
    return category


async def update_category(
    session: AsyncSession, user: User, category_id: uuid.UUID, data: CategoryUpdate
) -> Category:
    category = await category_repo.get_owned(session, user.id, category_id)
    if category is None:
        raise NotFoundError("Category")  # system categories are read-only
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await session.commit()
    await session.refresh(category)
    return category


async def delete_category(session: AsyncSession, user: User, category_id: uuid.UUID) -> None:
    category = await category_repo.get_owned(session, user.id, category_id)
    if category is None:
        raise NotFoundError("Category")
    fallback = await category_repo.get_system_by_name(session, "Other")
    if fallback is None:
        raise AppError("SEED_MISSING", "Default categories are not loaded.", 500)
    await category_repo.delete_reassigning(session, user.id, category, fallback.id)
    await session.commit()


async def list_rules(session: AsyncSession, user: User) -> Sequence[MerchantRule]:
    return await merchant_rule_repo.list_user(session, user.id)


async def create_rule(session: AsyncSession, user: User, data: MerchantRuleIn) -> MerchantRule:
    await require_visible(session, user, data.category_id)
    if data.match_type == MatchType.REGEX:
        try:
            re.compile(data.pattern)
        except re.error as exc:
            raise AppError("INVALID_REGEX", f"Pattern is not a valid regex: {exc}") from exc
    rule = await merchant_rule_repo.create(session, user.id, **data.model_dump())
    await session.commit()
    return rule


async def delete_rule(session: AsyncSession, user: User, rule_id: uuid.UUID) -> None:
    rule = await merchant_rule_repo.get_user(session, user.id, rule_id)
    if rule is None:
        raise NotFoundError("Rule")
    await merchant_rule_repo.delete(session, rule)
    await session.commit()
