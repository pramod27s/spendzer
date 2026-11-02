"""Load default categories and global merchant rules. Idempotent: safe to run on every start.

python -m app.seed.seed
"""

import asyncio
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models import Category, MerchantRule
from app.models.enums import Bucket, MatchType

_DIR = Path(__file__).parent


def _load(name: str) -> Any:
    with (_DIR / name).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


async def seed(session: AsyncSession) -> None:
    existing = {
        c.name: c
        for c in (await session.scalars(select(Category).where(Category.user_id.is_(None)))).all()
    }
    for bucket_name, items in _load("categories.yaml").items():
        for item in items:
            cat = existing.get(item["name"])
            if cat is None:
                cat = Category(user_id=None, name=item["name"])
                session.add(cat)
                existing[cat.name] = cat
            cat.bucket = Bucket(bucket_name)
            cat.icon = item["icon"]
            cat.color = item["color"]
    await session.flush()

    rules = (
        await session.scalars(select(MerchantRule).where(MerchantRule.user_id.is_(None)))
    ).all()
    have = {(r.pattern, r.category_id) for r in rules}
    for category_name, keywords in _load("merchant_keywords.yaml").items():
        category = existing[category_name]
        for keyword in keywords:
            pattern = str(keyword).lower().strip()
            if (pattern, category.id) in have:
                continue
            session.add(
                MerchantRule(
                    user_id=None,
                    pattern=pattern,
                    match_type=MatchType.CONTAINS,
                    category_id=category.id,
                    priority=100,
                )
            )
            have.add((pattern, category.id))
    await session.commit()


async def _main() -> None:
    async with SessionLocal() as session:
        await seed(session)
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(_main())
