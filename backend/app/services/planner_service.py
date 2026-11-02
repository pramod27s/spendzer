"""Next-month planner: savings first, then fit spending into what's left.

Steps (see the build spec): expected income -> savings target -> spendable -> fixed costs from
recurring charges -> one-off events -> per-category forecasts -> fit check -> suggested cuts.
"""

import calendar
import uuid
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.errors import AppError, NotFoundError
from app.engine.forecast import forecast, median_income
from app.engine.money import inr
from app.engine.plan_fit import FitItem, fit
from app.models import Category, MonthlyPlan, PlanItem, PlannedEvent, User
from app.models.enums import Bucket, PlanItemSource, PlanStatus, TxnKind
from app.repositories import analytics_repo, category_repo, plan_repo, recurring_repo
from app.schemas.plan import (
    CutOut,
    EventIn,
    EventOut,
    FitOut,
    GenerateIn,
    PlanItemIn,
    PlanItemOut,
    PlanOut,
    PlanUpdate,
)

ZERO = Decimal("0")
_SPEND_BUCKETS = (Bucket.FIXED, Bucket.VARIABLE, Bucket.DISCRETIONARY)


def first_of_month(d: date) -> date:
    return d.replace(day=1)


def last_of_month(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def parse_month(value: str) -> date:
    try:
        year, month = (int(p) for p in value.split("-"))
        return date(year, month, 1)
    except (ValueError, TypeError) as exc:
        raise AppError("INVALID_MONTH", "Month must look like 2026-11.") from exc


def _rupees(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- reads


async def close_finished_plans(session: AsyncSession, user: User) -> None:
    """A plan becomes closed on the 1st of the next month."""
    await plan_repo.close_before(session, user.id, first_of_month(clock.today()))
    await session.commit()


async def _require(session: AsyncSession, user: User, plan_id: uuid.UUID) -> MonthlyPlan:
    plan = await plan_repo.get(session, user.id, plan_id)
    if plan is None:
        raise NotFoundError("Plan")
    return plan


def _editable(plan: MonthlyPlan) -> None:
    if plan.status == PlanStatus.CLOSED:
        raise AppError("PLAN_CLOSED", "This month is closed. Plan the next one instead.", 409)


async def view(session: AsyncSession, plan: MonthlyPlan) -> PlanOut:
    items = await plan_repo.items(session, plan.id)
    events = await plan_repo.events(session, plan.id)
    spendable = plan.expected_income - plan.savings_target
    result = fit(
        [FitItem(i.id, i.category_id, i.bucket, i.source, i.planned_amount) for i in items],
        sum((e.amount for e in events), ZERO),
        spendable,
    )
    pct = (
        (plan.savings_target / plan.expected_income * 100).quantize(Decimal("0.1"))
        if plan.expected_income > 0
        else None
    )
    return PlanOut(
        id=plan.id,
        month=plan.month,
        status=plan.status,
        expected_income=plan.expected_income,
        income_basis=plan.income_basis,
        income_custom=plan.income_custom,
        savings_target=plan.savings_target,
        savings_pct=pct,
        savings_custom=plan.savings_custom,
        items=[PlanItemOut.model_validate(i) for i in items],
        events=[EventOut.model_validate(e) for e in events],
        fit=FitOut(
            spendable=result.spendable,
            fixed_total=result.fixed_total,
            variable_total=result.variable_total,
            discretionary_total=result.discretionary_total,
            events_total=result.events_total,
            planned_total=result.planned_total,
            gap=result.gap,
            status=result.status,
            cuts=[
                CutOut(
                    item_id=c.item_id,
                    category_id=c.category_id,
                    current=c.current,
                    suggested=c.suggested,
                    cut=c.amount,
                )
                for c in result.cuts
            ],
            gap_after_cuts=result.gap_after_cuts,
        ),
    )


async def get_plan(session: AsyncSession, user: User, plan_id: uuid.UUID) -> PlanOut:
    await close_finished_plans(session, user)
    return await view(session, await _require(session, user, plan_id))


async def list_plans(session: AsyncSession, user: User, month: date | None) -> list[MonthlyPlan]:
    await close_finished_plans(session, user)
    if month:
        plan = await plan_repo.get_by_month(session, user.id, month)
        return [plan] if plan else []
    return list(await plan_repo.list_for_user(session, user.id))


# ---------------------------------------------------------------- generation


async def _income_from_history(
    session: AsyncSession, user: User, month: date
) -> tuple[Decimal, str] | None:
    months = await analytics_repo.months_with_data(session, user.id, month, TxnKind.INCOME, 3)
    if not months:
        return None
    rows = {
        m: inc
        for m, inc, _ in await analytics_repo.monthly(
            session, user.id, min(months), last_of_month(max(months)), None
        )
    }
    f = median_income([rows.get(m, ZERO) for m in months], months)
    return f.amount, f.basis


async def _fixed_items(
    session: AsyncSession, user: User, cats: dict[uuid.UUID, Category], other_id: uuid.UUID
) -> dict[uuid.UUID, tuple[Decimal, str]]:
    """One fixed line per category, summing its active recurring charges."""
    lines: dict[uuid.UUID, list[tuple[str, Decimal]]] = defaultdict(list)
    for g in await recurring_repo.active_for_plan(session, user.id):
        category_id = g.category_id if g.category_id in cats else other_id
        lines[category_id].append((g.merchant, g.monthly_amount))
    out: dict[uuid.UUID, tuple[Decimal, str]] = {}
    for category_id, parts in lines.items():
        total = sum((a for _, a in parts), ZERO)
        names = " + ".join(f"{m} {inr(a)}" for m, a in sorted(parts, key=lambda p: -p[1]))
        out[category_id] = (total, f"Recurring: {names}")
    return out


async def _forecast_items(
    session: AsyncSession, user: User, month: date
) -> dict[uuid.UUID | None, tuple[Decimal, str]]:
    months = await analytics_repo.months_with_data(session, user.id, month, TxnKind.EXPENSE, 3)
    if not months:
        return {}
    rows = await analytics_repo.monthly_category_spend(
        session, user.id, min(months), last_of_month(max(months)), exclude_recurring=True
    )
    spend: dict[uuid.UUID | None, dict[date, Decimal]] = defaultdict(dict)
    for m, category_id, amount in rows:
        spend[category_id][m] = amount
    out: dict[uuid.UUID | None, tuple[Decimal, str]] = {}
    for category_id, by_month in spend.items():
        f = forecast([by_month.get(m, ZERO) for m in months], months)
        if f.amount > 0:
            out[category_id] = (f.amount, f.basis)
    return out


async def generate(session: AsyncSession, user: User, month: date, data: GenerateIn) -> PlanOut:
    month = first_of_month(month)
    plan = await plan_repo.get_by_month(session, user.id, month)
    if plan is not None and plan.status != PlanStatus.DRAFT:
        raise AppError(
            "PLAN_NOT_DRAFT", "This month's plan is already active. Edit its amounts instead.", 409
        )

    # 1. Expected income
    if data.expected_income is not None:
        income, basis, income_custom = data.expected_income, "Entered by you", True
    elif plan is not None and plan.income_custom:
        income, basis, income_custom = plan.expected_income, plan.income_basis, True
    else:
        history = await _income_from_history(session, user, month)
        if history is None:
            if plan is None:
                raise AppError(
                    "INCOME_REQUIRED",
                    "We couldn't find income in your history. Enter what you expect to earn.",
                    422,
                )
            income, basis = plan.expected_income, plan.income_basis
        else:
            income, basis = history
        income_custom = False

    # 2–3. Savings target, taken out first
    if data.savings_target_pct is not None:
        savings, savings_custom = _rupees(income * data.savings_target_pct / 100), True
    elif plan is not None and plan.savings_custom:
        savings, savings_custom = plan.savings_target, True
    else:
        savings, savings_custom = _rupees(income * user.monthly_savings_target_pct / 100), False

    if plan is None:
        plan = await plan_repo.add(
            session,
            MonthlyPlan(
                user_id=user.id, month=month, expected_income=income, savings_target=savings
            ),
        )
    plan.expected_income = income
    plan.income_basis = basis
    plan.income_custom = income_custom
    plan.savings_target = savings
    plan.savings_custom = savings_custom

    # 4–6. Fixed costs + forecasts. The user's own lines are never overwritten, and a
    # category the user has set by hand gets no generated line next to it.
    await plan_repo.delete_generated_items(session, plan.id)
    user_categories = {
        i.category_id
        for i in await plan_repo.items(session, plan.id)
        if i.source == PlanItemSource.USER
    }
    cats = {c.id: c for c in await category_repo.list_visible(session, user.id)}
    other = await category_repo.get_system_by_name(session, "Other")
    if other is None:
        raise AppError("SEED_MISSING", "Default categories are not loaded.", 500)

    new_items: list[PlanItem] = []
    for category_id, (amount, why) in (await _fixed_items(session, user, cats, other.id)).items():
        if category_id in user_categories:
            continue
        new_items.append(
            PlanItem(
                plan_id=plan.id,
                category_id=category_id,
                planned_amount=amount,
                bucket=Bucket.FIXED,
                source=PlanItemSource.FIXED,
                basis=why,
            )
        )
    for raw_id, (amount, why) in (await _forecast_items(session, user, month)).items():
        category_id = raw_id if raw_id in cats else other.id
        bucket = cats[category_id].bucket
        if category_id in user_categories or bucket not in _SPEND_BUCKETS:
            continue
        if any(
            i.category_id == category_id and i.source == PlanItemSource.FORECAST for i in new_items
        ):
            continue
        new_items.append(
            PlanItem(
                plan_id=plan.id,
                category_id=category_id,
                planned_amount=amount,
                bucket=bucket,
                source=PlanItemSource.FORECAST,
                basis=why,
            )
        )
    await plan_repo.add_items(session, new_items)
    await session.commit()
    await session.refresh(plan)
    return await view(session, plan)


# ---------------------------------------------------------------- edits


async def update_plan(
    session: AsyncSession, user: User, plan_id: uuid.UUID, data: PlanUpdate
) -> PlanOut:
    plan = await _require(session, user, plan_id)
    _editable(plan)
    if data.expected_income is not None:
        plan.expected_income = data.expected_income
        plan.income_basis = "Entered by you"
        plan.income_custom = True
        if not plan.savings_custom:
            plan.savings_target = _rupees(
                data.expected_income * user.monthly_savings_target_pct / 100
            )
    if data.savings_target is not None:
        plan.savings_target = data.savings_target
        plan.savings_custom = True
    await session.commit()
    await session.refresh(plan)
    return await view(session, plan)


async def _set_user_amount(
    session: AsyncSession, plan: MonthlyPlan, item: PlanItem, amount: Decimal, basis: str
) -> None:
    """An edited line becomes the user's own. If the category already has one, fold into it."""
    if item.source == PlanItemSource.USER:
        item.planned_amount = amount
        item.basis = basis
        return
    existing = next(
        (
            i
            for i in await plan_repo.items(session, plan.id)
            if i.category_id == item.category_id and i.source == PlanItemSource.USER
        ),
        None,
    )
    if existing is not None:
        existing.planned_amount += amount
        await plan_repo.delete_item(session, item)
    else:
        item.planned_amount = amount
        item.source = PlanItemSource.USER
        item.basis = basis


async def update_item(
    session: AsyncSession, user: User, plan_id: uuid.UUID, item_id: uuid.UUID, amount: Decimal
) -> PlanOut:
    plan = await _require(session, user, plan_id)
    _editable(plan)
    item = await plan_repo.get_item(session, plan.id, item_id)
    if item is None:
        raise NotFoundError("Plan item")
    previous = item.planned_amount
    await _set_user_amount(session, plan, item, amount, f"Set by you (was {inr(previous)})")
    await session.commit()
    return await view(session, plan)


async def add_item(
    session: AsyncSession, user: User, plan_id: uuid.UUID, data: PlanItemIn
) -> PlanOut:
    plan = await _require(session, user, plan_id)
    _editable(plan)
    category = await category_repo.get_visible(session, user.id, data.category_id)
    if category is None:
        raise NotFoundError("Category")
    if category.bucket not in _SPEND_BUCKETS:
        raise AppError("NOT_A_SPENDING_CATEGORY", "Only spending categories can be budgeted.")
    existing = next(
        (
            i
            for i in await plan_repo.items(session, plan.id)
            if i.category_id == category.id and i.source == PlanItemSource.USER
        ),
        None,
    )
    if existing is not None:
        existing.planned_amount = data.planned_amount
    else:
        await plan_repo.add_items(
            session,
            [
                PlanItem(
                    plan_id=plan.id,
                    category_id=category.id,
                    planned_amount=data.planned_amount,
                    bucket=category.bucket,
                    source=PlanItemSource.USER,
                    basis="Added by you",
                )
            ],
        )
    await session.commit()
    return await view(session, plan)


async def delete_item(
    session: AsyncSession, user: User, plan_id: uuid.UUID, item_id: uuid.UUID
) -> PlanOut:
    plan = await _require(session, user, plan_id)
    _editable(plan)
    item = await plan_repo.get_item(session, plan.id, item_id)
    if item is None:
        raise NotFoundError("Plan item")
    await plan_repo.delete_item(session, item)
    await session.commit()
    return await view(session, plan)


async def apply_suggestions(session: AsyncSession, user: User, plan_id: uuid.UUID) -> PlanOut:
    plan = await _require(session, user, plan_id)
    _editable(plan)
    current = await view(session, plan)
    for cut in current.fit.cuts:
        item = await plan_repo.get_item(session, plan.id, cut.item_id)
        if item is not None:
            await _set_user_amount(
                session, plan, item, cut.suggested, f"Trimmed from {inr(cut.current)} to fit"
            )
    await session.commit()
    return await view(session, plan)


async def add_event(
    session: AsyncSession, user: User, plan_id: uuid.UUID, data: EventIn
) -> PlanOut:
    plan = await _require(session, user, plan_id)
    _editable(plan)
    if data.category_id is not None:
        category = await category_repo.get_visible(session, user.id, data.category_id)
        if category is None:
            raise NotFoundError("Category")
    if data.expected_date and first_of_month(data.expected_date) != plan.month:
        raise AppError("DATE_OUTSIDE_MONTH", "Pick a date inside the plan's month.")
    await plan_repo.add_event(
        session,
        PlannedEvent(
            plan_id=plan.id,
            title=" ".join(data.title.split()),
            amount=data.amount,
            category_id=data.category_id,
            expected_date=data.expected_date,
        ),
    )
    await session.commit()
    return await view(session, plan)


async def delete_event(
    session: AsyncSession, user: User, plan_id: uuid.UUID, event_id: uuid.UUID
) -> PlanOut:
    plan = await _require(session, user, plan_id)
    _editable(plan)
    event = await plan_repo.get_event(session, plan.id, event_id)
    if event is None:
        raise NotFoundError("Event")
    await plan_repo.delete_event(session, event)
    await session.commit()
    return await view(session, plan)


async def activate(session: AsyncSession, user: User, plan_id: uuid.UUID) -> PlanOut:
    plan = await _require(session, user, plan_id)
    if plan.status != PlanStatus.DRAFT:
        raise AppError("PLAN_NOT_DRAFT", "Only a draft plan can be activated.", 409)
    plan.status = PlanStatus.ACTIVE
    await session.commit()
    await session.refresh(plan)
    return await view(session, plan)
