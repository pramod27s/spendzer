import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import date, time
from decimal import Decimal
from statistics import median

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.engine.enrich import CategoryRef, enrich, kind_for_category
from app.models import Transaction, User
from app.models.enums import CategorizedBy, Direction, TxnKind
from app.repositories import account_repo, category_repo, merchant_rule_repo, transaction_repo
from app.schemas.transaction import (
    PayeeStats,
    ReviewQueueOut,
    TransactionCreate,
    TransactionFilters,
    TransactionOut,
    TransactionUpdate,
)
from app.services import alert_service
from app.services.category_service import require_visible
from app.services.enrichment import build_context


async def list_transactions(
    session: AsyncSession, user: User, filters: TransactionFilters, *, offset: int, limit: int
) -> tuple[Sequence[Transaction], int]:
    return await transaction_repo.list_page(session, user.id, filters, offset=offset, limit=limit)


async def get_transaction(session: AsyncSession, user: User, txn_id: uuid.UUID) -> Transaction:
    txn = await transaction_repo.get(session, user.id, txn_id)
    if txn is None:
        raise NotFoundError("Transaction")
    return txn


async def create_manual(session: AsyncSession, user: User, data: TransactionCreate) -> Transaction:
    if data.account_id:
        account = await account_repo.get(session, user.id, data.account_id)
        if account is None:
            raise NotFoundError("Account")
    else:
        account = await account_repo.get_or_create_cash(session, user.id)

    merchant = " ".join(data.merchant.split())
    category_id: uuid.UUID | None
    ml_version: str | None = None
    if data.category_id:
        category = await require_visible(session, user, data.category_id)
        ref = CategoryRef(category.id, category.name, category.bucket)
        kind = data.kind or kind_for_category(ref, data.direction)
        category_id, categorized_by = category.id, CategorizedBy.USER
    else:
        ctx = await build_context(session, user, data.txn_date, data.txn_date)
        result = enrich(
            ctx,
            raw_description=merchant,
            txn_date=data.txn_date,
            amount=data.amount,
            direction=data.direction,
            merchant=merchant,
        )
        kind, category_id, categorized_by = result.kind, result.category_id, result.categorized_by
        ml_version = result.ml_model_version
        # Someone typing in a cash credit is telling us it's income.
        if data.direction == Direction.CREDIT and kind == TxnKind.UNKNOWN:
            kind = TxnKind.INCOME
        if data.kind:
            kind = data.kind

    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        upload_id=None,
        txn_date=data.txn_date,
        amount=data.amount,
        direction=data.direction,
        raw_description=merchant,
        merchant=merchant,
        category_id=category_id,
        kind=kind,
        categorized_by=categorized_by,
        ml_model_version=ml_version,
        note=data.note,
    )
    await transaction_repo.add(session, txn)
    await session.commit()
    await session.refresh(txn)
    await alert_service.refresh_months(session, user, txn.txn_date, txn.txn_date)
    return txn


async def review_queue(session: AsyncSession, user: User, limit: int = 100) -> ReviewQueueOut:
    other = await category_repo.get_system_by_name(session, "Other")
    uncategorized, unknown = await transaction_repo.review_queue(
        session, user.id, other.id if other else None, limit
    )
    merchants = sorted({t.merchant for t in uncategorized if t.merchant})
    history = await transaction_repo.payee_history(session, user.id, merchants)
    return ReviewQueueOut(
        uncategorized=[TransactionOut.model_validate(t) for t in uncategorized],
        unknown_credits=[TransactionOut.model_validate(t) for t in unknown],
        total=len(uncategorized) + len(unknown),
        payee_stats=payee_stats(history),
    )


def _time_of_day(t: time) -> str:
    if 5 <= t.hour < 12:
        return "morning"
    if 12 <= t.hour < 17:
        return "afternoon"
    if 17 <= t.hour < 21:
        return "evening"
    return "night"


def payee_stats(
    rows: Sequence[tuple[str, Decimal, date, time | None]],
) -> dict[str, PayeeStats]:
    """Per payee: how often, how much, and when — so "who was this?" has an answer."""
    by_payee: dict[str, list[tuple[Decimal, date, time | None]]] = defaultdict(list)
    for merchant, amount, day, at in rows:
        by_payee[merchant].append((amount, day, at))
    out: dict[str, PayeeStats] = {}
    for merchant, hits in by_payee.items():
        amounts = sorted(a for a, _, _ in hits)
        days = [d for _, d, _ in hits]
        slots = Counter(_time_of_day(t) for _, _, t in hits if t is not None)
        usual = None
        if slots:
            slot, n = slots.most_common(1)[0]
            usual = slot if n * 2 > sum(slots.values()) else None  # a clear majority only
        out[merchant] = PayeeStats(
            count=len(hits),
            min_amount=amounts[0],
            max_amount=amounts[-1],
            median_amount=Decimal(str(median(amounts))).quantize(Decimal("0.01")),
            first_date=min(days),
            last_date=max(days),
            usual_time=usual,
        )
    return out


async def bulk_categorize(
    session: AsyncSession, user: User, transaction_ids: Sequence[uuid.UUID], category_id: uuid.UUID
) -> int:
    """File several transactions under one category by hand (no merchant rules are created)."""
    category = await require_visible(session, user, category_id)
    ref = CategoryRef(category.id, category.name, category.bucket)
    txns = await transaction_repo.owned_ids(session, user.id, transaction_ids)
    for txn in txns:
        txn.category_id = category.id
        txn.categorized_by = CategorizedBy.USER
        txn.kind = kind_for_category(ref, txn.direction)
    await session.commit()
    if txns:
        dates = [t.txn_date for t in txns]
        await alert_service.refresh_months(session, user, min(dates), max(dates))
    return len(txns)


async def update_transaction(
    session: AsyncSession, user: User, txn_id: uuid.UUID, data: TransactionUpdate
) -> tuple[Transaction, int]:
    txn = await get_transaction(session, user, txn_id)
    fields = data.model_dump(exclude_unset=True)
    recategorized = 0

    if data.category_id is not None:
        category = await require_visible(session, user, data.category_id)
        ref = CategoryRef(category.id, category.name, category.bucket)
        txn.category_id = category.id
        txn.categorized_by = CategorizedBy.USER
        txn.kind = data.kind or kind_for_category(ref, txn.direction)

        if data.apply_to_merchant:
            if not txn.merchant:
                raise AppError(
                    "NO_MERCHANT", "This transaction has no merchant to apply a rule to."
                )
            await merchant_rule_repo.upsert_exact(session, user.id, txn.merchant, category.id)
            recategorized = await transaction_repo.recategorize_merchant(
                session,
                user.id,
                txn.merchant,
                category.id,
                {d: kind_for_category(ref, d) for d in Direction},
                exclude_id=txn.id,
            )
    elif data.kind is not None:
        txn.kind = data.kind
        txn.categorized_by = CategorizedBy.USER

    if "note" in fields:
        txn.note = data.note
    await session.commit()
    await session.refresh(txn)
    if data.category_id is not None or data.kind is not None:
        await alert_service.refresh_months(session, user, txn.txn_date, txn.txn_date)
    return txn, recategorized


async def delete_transaction(session: AsyncSession, user: User, txn_id: uuid.UUID) -> None:
    txn = await get_transaction(session, user, txn_id)
    if txn.upload_id is not None:
        raise AppError(
            "NOT_MANUAL", "Only manual entries can be deleted. Delete the upload instead.", 409
        )
    await transaction_repo.delete(session, txn)
    await session.commit()
