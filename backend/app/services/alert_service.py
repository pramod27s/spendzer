"""Generate in-app alerts. Each (type, category, month) fires at most once."""

import logging
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.errors import NotFoundError
from app.engine.alerts import (
    AlertDraft,
    BudgetLine,
    ExpectedIncome,
    RecurringCharge,
    Spend,
    anomaly_alerts,
    budget_alerts,
    income_missing_alerts,
    recurring_change_alerts,
    stale_data_alert,
)
from app.models import Alert, User
from app.models.enums import PlanStatus, TxnKind
from app.repositories import (
    alert_repo,
    category_repo,
    plan_repo,
    recurring_repo,
    transaction_repo,
    upload_repo,
)
from app.services.planner_service import close_finished_plans, first_of_month, last_of_month
from app.services.tracking_service import tracking

log = logging.getLogger(__name__)

ANOMALY_LOOKBACK_DAYS = 90
INCOME_LOOKBACK_MONTHS = 3


async def _expected_income(session: AsyncSession, user: User, month: date) -> list[ExpectedIncome]:
    """Payers who credited income in at least two of the last three months, and on which day."""
    start = first_of_month(month - timedelta(days=31 * INCOME_LOOKBACK_MONTHS))
    rows = await transaction_repo.counted_rows(
        session, user.id, TxnKind.INCOME, start, month - timedelta(days=1)
    )
    by_payer: dict[str, list[tuple[date, uuid.UUID | None]]] = defaultdict(list)
    for merchant, _, category_id, day in rows:
        if merchant:
            by_payer[merchant].append((day, category_id))
    out = []
    for merchant, hits in by_payer.items():
        if len({(d.year, d.month) for d, _ in hits}) >= 2:
            out.append(ExpectedIncome(merchant, hits[-1][1], int(median(d.day for d, _ in hits))))
    return out


async def build_drafts(
    session: AsyncSession, user: User, month: date, today: date
) -> list[AlertDraft]:
    month = first_of_month(month)
    end = last_of_month(month)
    is_current = month == first_of_month(today)
    names: dict[uuid.UUID | None, str] = {
        c.id: c.name for c in await category_repo.list_visible(session, user.id)
    }
    names[None] = "Uncategorized"
    drafts: list[AlertDraft] = []

    # Budget + pace: only against an active plan.
    plan = await plan_repo.get_by_month(session, user.id, month)
    active_plan = plan is not None and plan.status == PlanStatus.ACTIVE
    if active_plan:
        t = await tracking(session, user, month, today)
        drafts += budget_alerts(
            (
                BudgetLine(
                    r.category_id,
                    names.get(r.category_id, "Uncategorized"),
                    r.planned,
                    r.spent,
                    r.projected,
                    r.pace_warning,
                )
                for r in t.rows
            ),
            t.days_left if is_current else None,
        )

    # Unusual single payments, against the category's last 90 days.
    spends = await transaction_repo.counted_rows(session, user.id, TxnKind.EXPENSE, month, end)
    past = await transaction_repo.counted_rows(
        session,
        user.id,
        TxnKind.EXPENSE,
        month - timedelta(days=ANOMALY_LOOKBACK_DAYS),
        month - timedelta(days=1),
    )
    history: dict[uuid.UUID | None, list[Decimal]] = defaultdict(list)
    for _, amount, category_id, _ in past:
        history[category_id].append(amount)
    drafts += anomaly_alerts((Spend(m, a, c) for m, a, c, _ in spends), history, names)

    # Recurring charges whose price moved.
    latest: dict[str, Decimal] = {}
    for merchant, amount, _, _ in spends:  # oldest first, so the last write is the newest
        latest[merchant] = amount
    drafts += recurring_change_alerts(
        RecurringCharge(g.merchant, g.category_id, g.typical_amount, latest.get(g.merchant))
        for g in await recurring_repo.active_for_plan(session, user.id)
    )

    if is_current:
        received = {
            m
            for m, _, _, _ in await transaction_repo.counted_rows(
                session, user.id, TxnKind.INCOME, month, end
            )
        }
        drafts += income_missing_alerts(
            await _expected_income(session, user, month), received, today
        )
        if active_plan:
            last = await upload_repo.latest_upload_at(session, user.id)
            drafts += stale_data_alert(last.date() if last else None, today)
    return drafts


async def refresh(session: AsyncSession, user: User, month: date) -> int:
    """Add any new alerts for `month`. Returns how many were created."""
    today = clock.today()
    month = first_of_month(month)
    await close_finished_plans(session, user)
    drafts = await build_drafts(session, user, month, today)
    seen = await alert_repo.existing_keys(session, user.id, month)
    fresh: list[Alert] = []
    for d in drafts:
        key = (d.type, d.category_id)
        if key in seen:
            continue
        seen.add(key)
        fresh.append(
            Alert(
                user_id=user.id,
                type=d.type,
                message=d.message,
                category_id=d.category_id,
                month=month,
            )
        )
    if fresh:
        await alert_repo.add_many(session, fresh)
    await session.commit()
    return len(fresh)


async def refresh_months(session: AsyncSession, user: User, start: date, end: date) -> None:
    """After an upload: refresh every month it touched. Never fails the caller."""
    try:
        month = first_of_month(start)
        while month <= end:
            await refresh(session, user, month)
            month = first_of_month(month + timedelta(days=32))
    except Exception:
        log.exception("alert refresh failed user=%s", user.id)
        await session.rollback()


async def list_alerts(
    session: AsyncSession, user: User, unread_only: bool, limit: int
) -> tuple[list[Alert], int]:
    await refresh(session, user, clock.today())  # stale-data and income checks are time-based
    alerts = await alert_repo.list_for_user(session, user.id, unread_only=unread_only, limit=limit)
    return list(alerts), await alert_repo.unread_count(session, user.id)


async def mark_read(session: AsyncSession, user: User, alert_id: uuid.UUID) -> Alert:
    alert = await alert_repo.get(session, user.id, alert_id)
    if alert is None:
        raise NotFoundError("Alert")
    alert.read = True
    await session.commit()
    await session.refresh(alert)
    return alert


async def mark_all_read(session: AsyncSession, user: User) -> None:
    await alert_repo.mark_all_read(session, user.id)
    await session.commit()
