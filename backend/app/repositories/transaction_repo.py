import uuid
from collections.abc import Sequence
from datetime import date, time
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, and_, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Transaction
from app.models.enums import CategorizedBy, Direction, TxnKind
from app.schemas.transaction import TransactionFilters


def _filters(user_id: uuid.UUID, f: TransactionFilters) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = [Transaction.user_id == user_id]
    if f.start:
        conds.append(Transaction.txn_date >= f.start)
    if f.end:
        conds.append(Transaction.txn_date <= f.end)
    if f.category_id:
        conds.append(Transaction.category_id == f.category_id)
    if f.account_id:
        conds.append(Transaction.account_id == f.account_id)
    if f.kind:
        conds.append(Transaction.kind == f.kind)
    if f.direction:
        conds.append(Transaction.direction == f.direction)
    if f.merchant:
        conds.append(Transaction.merchant == f.merchant)
    if f.search:
        like = f"%{f.search.strip()}%"
        conds.append(
            or_(
                Transaction.merchant.ilike(like),
                Transaction.raw_description.ilike(like),
                Transaction.note.ilike(like),
            )
        )
    if f.min_amount is not None:
        conds.append(Transaction.amount >= f.min_amount)
    if f.max_amount is not None:
        conds.append(Transaction.amount <= f.max_amount)
    return conds


async def list_page(
    session: AsyncSession,
    user_id: uuid.UUID,
    filters: TransactionFilters,
    *,
    offset: int,
    limit: int,
) -> tuple[Sequence[Transaction], int]:
    conds = _filters(user_id, filters)
    total = await session.scalar(select(func.count(Transaction.id)).where(*conds)) or 0
    stmt = (
        select(Transaction)
        .where(*conds)
        .order_by(Transaction.txn_date.desc(), Transaction.created_at.desc(), Transaction.id)
        .offset(offset)
        .limit(limit)
    )
    return (await session.scalars(stmt)).all(), total


async def get(session: AsyncSession, user_id: uuid.UUID, txn_id: uuid.UUID) -> Transaction | None:
    return await session.scalar(
        select(Transaction).where(Transaction.id == txn_id, Transaction.user_id == user_id)
    )


async def bulk_insert(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if rows:
        await session.execute(insert(Transaction), rows)


async def add(session: AsyncSession, txn: Transaction) -> Transaction:
    session.add(txn)
    await session.flush()
    return txn


async def delete(session: AsyncSession, txn: Transaction) -> None:
    await session.delete(txn)


async def history(
    session: AsyncSession, user_id: uuid.UUID, direction: Direction, start: date, end: date
) -> Sequence[tuple[date, Decimal, str]]:
    """(date, amount, merchant) rows used by refund and salary-pattern checks."""
    stmt = select(Transaction.txn_date, Transaction.amount, Transaction.merchant).where(
        Transaction.user_id == user_id,
        Transaction.direction == direction,
        Transaction.txn_date.between(start, end),
    )
    return [(d, a, m) for d, a, m in (await session.execute(stmt)).all()]


async def recategorize_merchant(
    session: AsyncSession,
    user_id: uuid.UUID,
    merchant: str,
    category_id: uuid.UUID,
    kind_by_direction: dict[Direction, TxnKind],
    exclude_id: uuid.UUID,
) -> int:
    """Point every non-hand-set transaction from `merchant` at `category_id`."""
    moved = 0
    for direction, kind in kind_by_direction.items():
        result = await session.execute(
            update(Transaction)
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.merchant == merchant,
                    Transaction.direction == direction,
                    Transaction.categorized_by != CategorizedBy.USER,
                    Transaction.id != exclude_id,
                )
            )
            .values(category_id=category_id, kind=kind, categorized_by=CategorizedBy.OVERRIDE)
        )
        moved += result.rowcount or 0  # type: ignore[attr-defined]
    return moved


async def expense_debits(
    session: AsyncSession, user_id: uuid.UUID
) -> Sequence[tuple[uuid.UUID, str, date, Decimal, uuid.UUID | None]]:
    """(id, merchant, date, amount, category_id) of every counted spend, for recurring detection."""
    stmt = select(
        Transaction.id,
        Transaction.merchant,
        Transaction.txn_date,
        Transaction.amount,
        Transaction.category_id,
    ).where(
        Transaction.user_id == user_id,
        Transaction.kind == TxnKind.EXPENSE,
        Transaction.direction == Direction.DEBIT,
        Transaction.dedup_of.is_(None),
    )
    return [tuple(r) for r in (await session.execute(stmt)).all()]  # type: ignore[misc]


async def transfer_candidates(
    session: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> Sequence[Transaction]:
    """Rows that could be one side of a transfer between the user's own accounts.

    Debits counted as spending and credits we couldn't explain; anything the user set by hand
    is left alone.
    """
    stmt = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.txn_date.between(start, end),
        Transaction.dedup_of.is_(None),
        Transaction.categorized_by != CategorizedBy.USER,
        or_(
            and_(Transaction.direction == Direction.DEBIT, Transaction.kind == TxnKind.EXPENSE),
            and_(Transaction.direction == Direction.CREDIT, Transaction.kind == TxnKind.UNKNOWN),
        ),
    )
    return (await session.scalars(stmt)).all()


async def mark_kind(
    session: AsyncSession,
    user_id: uuid.UUID,
    ids: Sequence[uuid.UUID],
    kind: TxnKind,
    category_id: uuid.UUID | None,
) -> None:
    if not ids:
        return
    await session.execute(
        update(Transaction)
        .where(Transaction.user_id == user_id, Transaction.id.in_(ids))
        .values(kind=kind, category_id=category_id, categorized_by=CategorizedBy.RULE)
    )


async def counted_rows(
    session: AsyncSession, user_id: uuid.UUID, kind: TxnKind, start: date, end: date
) -> Sequence[tuple[str, Decimal, uuid.UUID | None, date]]:
    """(merchant, amount, category_id, date) of counted rows of one kind, oldest first."""
    stmt = (
        select(
            Transaction.merchant, Transaction.amount, Transaction.category_id, Transaction.txn_date
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.kind == kind,
            Transaction.dedup_of.is_(None),
            Transaction.txn_date.between(start, end),
        )
        .order_by(Transaction.txn_date)
    )
    return [(m, a, c, d) for m, a, c, d in (await session.execute(stmt)).all()]


async def review_queue(
    session: AsyncSession, user_id: uuid.UUID, other_category_id: uuid.UUID | None, limit: int
) -> tuple[Sequence[Transaction], Sequence[Transaction]]:
    """(spends we couldn't categorize, credits we couldn't explain), newest first."""
    base = select(Transaction).where(Transaction.user_id == user_id, Transaction.dedup_of.is_(None))
    uncategorized = await session.scalars(
        base.where(
            Transaction.kind == TxnKind.EXPENSE,
            Transaction.categorized_by == CategorizedBy.RULE,
            or_(Transaction.category_id.is_(None), Transaction.category_id == other_category_id),
        )
        .order_by(Transaction.txn_date.desc())
        .limit(limit)
    )
    unknown = await session.scalars(
        base.where(Transaction.kind == TxnKind.UNKNOWN, Transaction.direction == Direction.CREDIT)
        .order_by(Transaction.txn_date.desc())
        .limit(limit)
    )
    return uncategorized.all(), unknown.all()


async def dedup_candidates(
    session: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> Sequence[tuple[Transaction, str]]:
    """Imported, not-yet-deduplicated rows in a window, with their account's type."""
    stmt = (
        select(Transaction, Account.type)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.upload_id.is_not(None),
            Transaction.dedup_of.is_(None),
            Transaction.txn_date.between(start, end),
        )
    )
    return [(t, str(k)) for t, k in (await session.execute(stmt)).all()]


async def mark_duplicates(
    session: AsyncSession, user_id: uuid.UUID, pairs: Sequence[tuple[uuid.UUID, uuid.UUID]]
) -> None:
    for dup_id, keep_id in pairs:
        await session.execute(
            update(Transaction)
            .where(Transaction.user_id == user_id, Transaction.id == dup_id)
            .values(dedup_of=keep_id)
        )


async def payee_history(
    session: AsyncSession, user_id: uuid.UUID, merchants: Sequence[str]
) -> Sequence[tuple[str, Decimal, date, time | None]]:
    """(merchant, amount, date, time) of every counted spend to these payees."""
    if not merchants:
        return []
    stmt = select(
        Transaction.merchant, Transaction.amount, Transaction.txn_date, Transaction.txn_time
    ).where(
        Transaction.user_id == user_id,
        Transaction.merchant.in_(merchants),
        Transaction.kind == TxnKind.EXPENSE,
        Transaction.dedup_of.is_(None),
    )
    return [(m, a, d, t) for m, a, d, t in (await session.execute(stmt)).all()]


async def owned_ids(
    session: AsyncSession, user_id: uuid.UUID, ids: Sequence[uuid.UUID]
) -> Sequence[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user_id, Transaction.id.in_(ids))
    return (await session.scalars(stmt)).all()
