"""Build the per-user context the enrichment engine needs (rules, categories, history)."""

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.categorizer import Categorizer, RuleSpec
from app.engine.enrich import CategoryRef, EnrichContext
from app.engine.income import PastTxn
from app.engine.transfers import OwnIdentity
from app.ml.model import MIN_CONFIDENCE, get_model
from app.models import User
from app.models.enums import Direction
from app.repositories import account_repo, category_repo, merchant_rule_repo, transaction_repo


async def build_context(session: AsyncSession, user: User, start: date, end: date) -> EnrichContext:
    rules = await merchant_rule_repo.list_with_buckets(session, user.id)
    categorizer = Categorizer(
        RuleSpec(
            pattern=rule.pattern,
            match_type=rule.match_type,
            category_id=rule.category_id,
            bucket=bucket,
            priority=rule.priority,
            is_user=rule.user_id is not None,
        )
        for rule, bucket in rules
    )
    # System categories last so they win name lookups ("Other", "Salary", ...) even if the
    # user created a category with the same name.
    visible = await category_repo.list_visible(session, user.id)
    categories = [
        CategoryRef(c.id, c.name, c.bucket)
        for c in sorted(visible, key=lambda c: c.user_id is None)
    ]
    accounts = await account_repo.list_for_user(session, user.id)
    identity = OwnIdentity(
        user_name=user.name, last4s=frozenset(a.last4 for a in accounts if a.last4)
    )
    debits = await transaction_repo.history(
        session, user.id, Direction.DEBIT, start - timedelta(days=31), end
    )
    credits = await transaction_repo.history(
        session, user.id, Direction.CREDIT, start - timedelta(days=100), end
    )
    return EnrichContext(
        ml=get_model(),
        ml_min_confidence=MIN_CONFIDENCE,
        categorizer=categorizer,
        identity=identity,
        categories=categories,
        recent_debits=[PastTxn(d, a, m) for d, a, m in debits],
        past_credits=[PastTxn(d, a, m) for d, a, m in credits],
    )
