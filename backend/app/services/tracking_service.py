"""During the month: am I on track? Plan vs actual, safe-to-spend and pace."""

import calendar
import uuid
from collections import defaultdict
from datetime import date
from decimal import ROUND_DOWN, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.errors import AppError
from app.models import User
from app.models.enums import Bucket
from app.repositories import analytics_repo, category_repo, plan_repo
from app.schemas.plan import TrackingOut, TrackingRow
from app.services.planner_service import close_finished_plans, first_of_month, last_of_month

ZERO = Decimal("0")
WARN_AT = Decimal("80")
PACE_TOLERANCE = Decimal("1.1")
PACE_MIN_DAYS = 7
FLEXIBLE = (Bucket.VARIABLE, Bucket.DISCRETIONARY)


def _status(planned: Decimal, spent: Decimal) -> tuple[Decimal | None, str]:
    if planned <= 0:
        return None, "over" if spent > 0 else "on_track"
    pct = (spent / planned * 100).quantize(Decimal("0.1"))
    if pct > 100:
        return pct, "over"
    if pct >= WARN_AT:
        return pct, "warning"
    return pct, "on_track"


def month_progress(month: date, today: date) -> tuple[int, int, int]:
    """(days in month, days elapsed, days left including today)."""
    days = calendar.monthrange(month.year, month.month)[1]
    if today < month:
        return days, 0, days
    if today > last_of_month(month):
        return days, days, 0
    return days, today.day, days - today.day + 1


async def tracking(
    session: AsyncSession, user: User, month: date | None = None, today: date | None = None
) -> TrackingOut:
    today = today or clock.today()
    month = first_of_month(month or today)
    await close_finished_plans(session, user)
    plan = await plan_repo.get_by_month(session, user.id, month)
    if plan is None:
        raise AppError("NO_PLAN", "There's no plan for this month yet.", 404)

    cats = {c.id: c for c in await category_repo.list_visible(session, user.id)}

    def bucket_of(category_id: uuid.UUID | None) -> Bucket:
        cat = cats.get(category_id) if category_id else None
        return (
            cat.bucket if cat and cat.bucket in (Bucket.FIXED, *FLEXIBLE) else Bucket.DISCRETIONARY
        )

    planned: dict[uuid.UUID | None, Decimal] = defaultdict(lambda: ZERO)
    buckets: dict[uuid.UUID | None, Bucket] = {}
    for item in await plan_repo.items(session, plan.id):
        planned[item.category_id] += item.planned_amount
        buckets.setdefault(item.category_id, item.bucket)
    for event in await plan_repo.events(session, plan.id):
        planned[event.category_id] += event.amount
        buckets.setdefault(event.category_id, bucket_of(event.category_id))

    end = last_of_month(month)
    spent = {
        c: amount
        for c, amount, _ in await analytics_repo.spending_by_category(
            session, user.id, month, end, None
        )
    }
    income, spending, _ = await analytics_repo.totals(session, user.id, month, end, None)
    days, elapsed, days_left = month_progress(month, today)
    in_progress = elapsed > 0 and days_left > 0  # today falls inside this month

    rows: list[TrackingRow] = []
    flexible_planned = flexible_spent = ZERO
    for category_id in set(planned) | set(spent):
        p, s = planned.get(category_id, ZERO), spent.get(category_id, ZERO)
        pct, status = _status(p, s)
        bucket = buckets.get(category_id) or bucket_of(category_id)
        projected: Decimal | None = None
        pace_warning = False
        if bucket in FLEXIBLE:
            flexible_planned += p
            flexible_spent += s
            if elapsed > 0:
                projected = (s / elapsed * days).quantize(Decimal("1"))
                pace_warning = (
                    in_progress
                    and elapsed >= PACE_MIN_DAYS
                    and p > 0
                    and projected > p * PACE_TOLERANCE
                    and status != "over"  # already over: the budget alert says so
                )
        rows.append(
            TrackingRow(
                category_id=category_id,
                bucket=bucket,
                planned=p,
                spent=s,
                remaining=p - s,
                pct_used=pct,
                status=status,
                projected=projected,
                pace_warning=pace_warning,
            )
        )
    rows.sort(key=lambda r: (-r.planned, -r.spent))

    safe: Decimal | None = None
    if days_left > 0:
        safe = max(ZERO, (flexible_planned - flexible_spent) / days_left).quantize(
            Decimal("1"), rounding=ROUND_DOWN
        )

    planned_total = sum(planned.values(), ZERO)
    return TrackingOut(
        plan_id=plan.id,
        month=month,
        status=plan.status,
        expected_income=plan.expected_income,
        actual_income=income,
        savings_target=plan.savings_target,
        planned_total=planned_total,
        spent_total=spending,
        remaining_total=planned_total - spending,
        days_in_month=days,
        days_elapsed=elapsed,
        days_left=days_left,
        flexible_planned=flexible_planned,
        flexible_spent=flexible_spent,
        safe_to_spend=safe,
        rows=rows,
    )
