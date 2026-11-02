"""Aggregations for analytics. Spending = kind 'expense', income = kind 'income';
rows marked as duplicates (dedup_of set) never count."""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import ColumnElement, Date, case, cast, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction
from app.models.enums import TxnKind

ZERO = Decimal("0")


def _scope(
    user_id: uuid.UUID, start: date, end: date, account_id: uuid.UUID | None
) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = [
        Transaction.user_id == user_id,
        Transaction.txn_date.between(start, end),
        Transaction.dedup_of.is_(None),
    ]
    if account_id:
        conds.append(Transaction.account_id == account_id)
    return conds


def _sum_kind(kind: TxnKind) -> ColumnElement[Decimal]:
    return func.coalesce(func.sum(case((Transaction.kind == kind, Transaction.amount), else_=0)), 0)


async def totals(
    session: AsyncSession, user_id: uuid.UUID, start: date, end: date, account_id: uuid.UUID | None
) -> tuple[Decimal, Decimal, int]:
    """(income, spending, transaction count)."""
    row = (
        await session.execute(
            select(
                _sum_kind(TxnKind.INCOME),
                _sum_kind(TxnKind.EXPENSE),
                func.count(Transaction.id),
            ).where(*_scope(user_id, start, end, account_id))
        )
    ).one()
    return Decimal(row[0]), Decimal(row[1]), int(row[2])


async def spending_by_category(
    session: AsyncSession, user_id: uuid.UUID, start: date, end: date, account_id: uuid.UUID | None
) -> Sequence[tuple[uuid.UUID | None, Decimal, int]]:
    stmt = (
        select(Transaction.category_id, func.sum(Transaction.amount), func.count(Transaction.id))
        .where(*_scope(user_id, start, end, account_id), Transaction.kind == TxnKind.EXPENSE)
        .group_by(Transaction.category_id)
        .order_by(func.sum(Transaction.amount).desc())
    )
    return [(c, Decimal(a), int(n)) for c, a, n in (await session.execute(stmt)).all()]


async def monthly(
    session: AsyncSession, user_id: uuid.UUID, start: date, end: date, account_id: uuid.UUID | None
) -> Sequence[tuple[date, Decimal, Decimal]]:
    month = cast(func.date_trunc("month", Transaction.txn_date), Date).label("month")
    stmt = (
        select(month, _sum_kind(TxnKind.INCOME), _sum_kind(TxnKind.EXPENSE))
        .where(*_scope(user_id, start, end, account_id))
        .group_by(month)
        .order_by(month)
    )
    return [(m, Decimal(i), Decimal(s)) for m, i, s in (await session.execute(stmt)).all()]


async def top_merchants(
    session: AsyncSession,
    user_id: uuid.UUID,
    start: date,
    end: date,
    account_id: uuid.UUID | None,
    limit: int = 10,
) -> Sequence[tuple[str, Decimal, int, uuid.UUID | None]]:
    latest_category = func.array_agg(
        aggregate_order_by(Transaction.category_id, Transaction.txn_date.desc())
    )[1]
    stmt = (
        select(
            Transaction.merchant,
            func.sum(Transaction.amount),
            func.count(Transaction.id),
            latest_category,
        )
        .where(
            *_scope(user_id, start, end, account_id),
            Transaction.kind == TxnKind.EXPENSE,
            Transaction.merchant != "",
        )
        .group_by(Transaction.merchant)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(limit)
    )
    return [(m, Decimal(a), int(n), c) for m, a, n, c in (await session.execute(stmt)).all()]


async def daily_spending(
    session: AsyncSession, user_id: uuid.UUID, start: date, end: date, account_id: uuid.UUID | None
) -> Sequence[tuple[date, Decimal]]:
    stmt = (
        select(Transaction.txn_date, func.sum(Transaction.amount))
        .where(*_scope(user_id, start, end, account_id), Transaction.kind == TxnKind.EXPENSE)
        .group_by(Transaction.txn_date)
        .order_by(Transaction.txn_date)
    )
    return [(d, Decimal(a)) for d, a in (await session.execute(stmt)).all()]


async def data_bounds(session: AsyncSession, user_id: uuid.UUID) -> tuple[date | None, date | None]:
    row = (
        await session.execute(
            select(func.min(Transaction.txn_date), func.max(Transaction.txn_date)).where(
                Transaction.user_id == user_id
            )
        )
    ).one()
    return row[0], row[1]


async def months_with_data(
    session: AsyncSession, user_id: uuid.UUID, before: date, kind: TxnKind, limit: int = 3
) -> list[date]:
    """The most recent months (first day) before `before` holding any `kind` rows, newest first."""
    month = cast(func.date_trunc("month", Transaction.txn_date), Date).label("month")
    stmt = (
        select(month)
        .where(
            Transaction.user_id == user_id,
            Transaction.txn_date < before,
            Transaction.kind == kind,
            Transaction.dedup_of.is_(None),
        )
        .group_by(month)
        .order_by(month.desc())
        .limit(limit)
    )
    return [m for (m,) in (await session.execute(stmt)).all()]


async def monthly_category_spend(
    session: AsyncSession, user_id: uuid.UUID, start: date, end: date, exclude_recurring: bool
) -> Sequence[tuple[date, uuid.UUID | None, Decimal]]:
    month = cast(func.date_trunc("month", Transaction.txn_date), Date).label("month")
    conds = [
        *_scope(user_id, start, end, None),
        Transaction.kind == TxnKind.EXPENSE,
    ]
    if exclude_recurring:
        conds.append(Transaction.is_recurring.is_(False))
    stmt = (
        select(month, Transaction.category_id, func.sum(Transaction.amount))
        .where(*conds)
        .group_by(month, Transaction.category_id)
    )
    return [(m, c, Decimal(a)) for m, c, a in (await session.execute(stmt)).all()]
