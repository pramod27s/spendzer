"""Month-end review: planned vs actual, savings hit or missed, overspends and wins."""

import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.repositories import plan_repo
from app.schemas.plan import PlannedActual, ReviewCategory, ReviewOut
from app.services import analytics_service
from app.services.planner_service import close_finished_plans, last_of_month
from app.services.tracking_service import tracking

ZERO = Decimal("0")
ON_TARGET_BAND = Decimal("0.05")  # within 5% of plan counts as on target


def _label(planned: Decimal, actual: Decimal) -> str:
    if planned <= 0:
        return "unplanned"
    if actual > planned:
        return "over"
    if actual < planned * (1 - ON_TARGET_BAND):
        return "under"
    return "on_target"


async def review(session: AsyncSession, user: User, plan_id: uuid.UUID) -> ReviewOut:
    await close_finished_plans(session, user)
    plan = await plan_repo.get(session, user.id, plan_id)
    if plan is None:
        raise NotFoundError("Plan")
    t = await tracking(session, user, plan.month)

    categories = [
        ReviewCategory(
            category_id=r.category_id,
            bucket=r.bucket,
            planned=r.planned,
            actual=r.spent,
            diff=r.planned - r.spent,
            label=_label(r.planned, r.spent),
        )
        for r in t.rows
    ]
    overspends = sorted((c for c in categories if c.diff < 0), key=lambda c: c.diff)[:3]
    wins = sorted(
        (c for c in categories if c.planned > 0 and c.diff > 0), key=lambda c: c.diff, reverse=True
    )[:3]

    actual_savings = t.actual_income - t.spent_total
    insight_cards = await analytics_service.insights(session, user, plan.month)
    next_month = last_of_month(plan.month) + timedelta(days=1)
    return ReviewOut(
        plan_id=plan.id,
        month=plan.month,
        status=plan.status,
        next_month=next_month.strftime("%Y-%m"),
        income=PlannedActual(planned=plan.expected_income, actual=t.actual_income),
        spending=PlannedActual(planned=t.planned_total, actual=t.spent_total),
        savings=PlannedActual(planned=plan.savings_target, actual=actual_savings),
        savings_hit=actual_savings >= plan.savings_target,
        savings_diff=actual_savings - plan.savings_target,
        categories=categories,
        overspends=overspends,
        wins=wins,
        insights=insight_cards.insights[:3],
    )
