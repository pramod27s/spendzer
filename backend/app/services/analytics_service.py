import calendar
import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.engine.insights import MerchantStat, MonthFacts
from app.engine.insights import build as build_insights
from app.models import User
from app.models.enums import Bucket, TxnKind
from app.repositories import analytics_repo, category_repo, plan_repo, recurring_repo
from app.schemas.analytics import (
    BucketSlice,
    CategoriesOut,
    CategorySlice,
    DailyOut,
    DayPoint,
    InsightOut,
    InsightsOut,
    MerchantRow,
    MerchantsOut,
    PeriodName,
    PeriodOut,
    SummaryOut,
    Totals,
    TrendOut,
    TrendPoint,
    WeekdayPoint,
)

ZERO = Decimal("0")
_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_SPEND_BUCKETS = (Bucket.FIXED, Bucket.VARIABLE, Bucket.DISCRETIONARY)


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _add_months(d: date, months: int) -> date:
    idx = d.year * 12 + (d.month - 1) + months
    year, month = divmod(idx, 12)
    return date(year, month + 1, 1)


def _pct(part: Decimal, whole: Decimal) -> Decimal | None:
    if whole <= 0:
        return None
    return (part / whole * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _label(start: date, end: date) -> str:
    if start == _month_start(start) and end == _month_end(start):
        return start.strftime("%B %Y")
    if start.year == end.year:
        return f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"
    return f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"


def resolve_period(
    name: PeriodName, start: date | None, end: date | None, today: date | None = None
) -> tuple[PeriodOut, PeriodOut]:
    """Return (period, previous period of equal length)."""
    today = today or date.today()
    this_month = _month_start(today)
    months = {"this_month": 1, "last_3": 3, "last_6": 6, "last_12": 12}

    if name == "custom":
        if not start or not end:
            raise AppError("INVALID_PERIOD", "A custom period needs start and end dates.")
        if end < start:
            raise AppError("INVALID_PERIOD", "End date must be on or after the start date.")
        if (end - start).days > 366 * 3:
            raise AppError("INVALID_PERIOD", "Custom periods can span at most 3 years.")
        whole_months = start == _month_start(start) and end == _month_end(end)
        if whole_months:
            span = (end.year - start.year) * 12 + end.month - start.month + 1
            p_start, p_end = _add_months(start, -span), start - timedelta(days=1)
        else:
            length = (end - start).days + 1
            p_start, p_end = start - timedelta(days=length), start - timedelta(days=1)
    elif name == "last_month":
        start = _add_months(this_month, -1)
        end = this_month - timedelta(days=1)
        p_start, p_end = _add_months(start, -1), start - timedelta(days=1)
    else:
        n = months[name]
        start = _add_months(this_month, -(n - 1))
        end = _month_end(today)
        p_start, p_end = _add_months(start, -n), start - timedelta(days=1)

    period = PeriodOut(name=name, start=start, end=end, label=_label(start, end))
    previous = PeriodOut(name="custom", start=p_start, end=p_end, label=_label(p_start, p_end))
    return period, previous


def _totals(income: Decimal, spending: Decimal) -> Totals:
    net = income - spending
    return Totals(income=income, spending=spending, net_savings=net, savings_rate=_pct(net, income))


async def summary(
    session: AsyncSession,
    user: User,
    period: PeriodOut,
    previous: PeriodOut,
    account_id: uuid.UUID | None,
) -> SummaryOut:
    income, spending, count = await analytics_repo.totals(
        session, user.id, period.start, period.end, account_id
    )
    p_income, p_spending, _ = await analytics_repo.totals(
        session, user.id, previous.start, previous.end, account_id
    )
    _, latest = await analytics_repo.data_bounds(session, user.id)
    current = _totals(income, spending)
    return SummaryOut(
        **current.model_dump(),
        period=period,
        txn_count=count,
        previous=_totals(p_income, p_spending),
        has_data=count > 0,
        latest_txn_date=latest,
    )


async def categories(
    session: AsyncSession, user: User, period: PeriodOut, account_id: uuid.UUID | None
) -> CategoriesOut:
    rows = await analytics_repo.spending_by_category(
        session, user.id, period.start, period.end, account_id
    )
    income, spending, _ = await analytics_repo.totals(
        session, user.id, period.start, period.end, account_id
    )
    cats = {c.id: c for c in await category_repo.list_visible(session, user.id)}

    slices: list[CategorySlice] = []
    by_bucket: dict[Bucket, Decimal] = dict.fromkeys(_SPEND_BUCKETS, ZERO)
    for category_id, amount, count in rows:
        cat = cats.get(category_id) if category_id else None
        bucket = cat.bucket if cat else Bucket.DISCRETIONARY
        slices.append(
            CategorySlice(
                category_id=category_id,
                name=cat.name if cat else "Uncategorized",
                icon=cat.icon if cat else "circle-dashed",
                color=cat.color if cat else "#898781",
                bucket=bucket,
                amount=amount,
                pct=_pct(amount, spending) or ZERO,
                count=count,
            )
        )
        if bucket in by_bucket:
            by_bucket[bucket] += amount
        else:  # an expense sitting in an income/excluded category: treat as discretionary
            by_bucket[Bucket.DISCRETIONARY] += amount

    buckets = [
        BucketSlice(
            bucket=b,
            amount=by_bucket[b],
            pct_of_spending=_pct(by_bucket[b], spending) or ZERO,
            pct_of_income=_pct(by_bucket[b], income),
        )
        for b in _SPEND_BUCKETS
    ]
    return CategoriesOut(
        period=period, total=spending, income=income, categories=slices, buckets=buckets
    )


async def trend(
    session: AsyncSession,
    user: User,
    months: int,
    end_month: date | None,
    account_id: uuid.UUID | None,
) -> TrendOut:
    last = _month_start(end_month or date.today())
    first = _add_months(last, -(months - 1))
    rows = {
        m: (i, s)
        for m, i, s in await analytics_repo.monthly(
            session, user.id, first, _month_end(last), account_id
        )
    }
    points = []
    for k in range(months):
        m = _add_months(first, k)
        income, spending = rows.get(m, (ZERO, ZERO))
        points.append(
            TrendPoint(
                month=m.strftime("%Y-%m"),
                income=income,
                spending=spending,
                savings=income - spending,
            )
        )
    return TrendOut(points=points)


async def merchants(
    session: AsyncSession,
    user: User,
    period: PeriodOut,
    account_id: uuid.UUID | None,
    limit: int = 10,
) -> MerchantsOut:
    rows = await analytics_repo.top_merchants(
        session, user.id, period.start, period.end, account_id, limit
    )
    return MerchantsOut(
        period=period,
        merchants=[
            MerchantRow(merchant=m, amount=a, count=n, category_id=c) for m, a, n, c in rows
        ],
    )


async def daily(
    session: AsyncSession,
    user: User,
    period: PeriodOut,
    account_id: uuid.UUID | None,
    today: date | None = None,
) -> DailyOut:
    today = today or date.today()
    last_day = min(period.end, max(today, period.start))
    rows = dict(
        await analytics_repo.daily_spending(session, user.id, period.start, last_day, account_id)
    )
    days: list[DayPoint] = []
    weekday_total = [ZERO] * 7
    weekday_count = [0] * 7
    d = period.start
    while d <= last_day:
        amount = rows.get(d, ZERO)
        days.append(DayPoint(date=d, amount=amount))
        weekday_total[d.weekday()] += amount
        weekday_count[d.weekday()] += 1
        d += timedelta(days=1)
    weekdays = [
        WeekdayPoint(
            weekday=i,
            label=_WEEKDAYS[i],
            average=(weekday_total[i] / weekday_count[i]).quantize(Decimal("0.01"))
            if weekday_count[i]
            else ZERO,
        )
        for i in range(7)
    ]
    return DailyOut(period=period, days=days, weekdays=weekdays)


async def insights(session: AsyncSession, user: User, month: date) -> InsightsOut:
    """3–5 plain-language insight cards for a month, ranked by rupee impact."""
    month = _month_start(month)
    end = _month_end(month)
    cats = {c.id: c for c in await category_repo.list_visible(session, user.id)}
    names: dict[uuid.UUID | None, str] = {c.id: c.name for c in cats.values()}

    spend = {
        c: a
        for c, a, _ in await analytics_repo.spending_by_category(session, user.id, month, end, None)
    }
    months = await analytics_repo.months_with_data(session, user.id, month, TxnKind.EXPENSE, 3)
    history: dict[uuid.UUID | None, list[Decimal]] = {}
    if months:
        for _, category_id, amount in await analytics_repo.monthly_category_spend(
            session, user.id, min(months), _month_end(max(months)), exclude_recurring=False
        ):
            history.setdefault(category_id, []).append(amount)
    income, spending, _ = await analytics_repo.totals(session, user.id, month, end, None)

    plan = await plan_repo.get_by_month(session, user.id, month)
    if plan is not None and plan.expected_income > 0:
        target_pct = plan.savings_target / plan.expected_income * 100
    else:
        target_pct = user.monthly_savings_target_pct
    fixed = sum((a for c, a in spend.items() if c in cats and cats[c].bucket == Bucket.FIXED), ZERO)
    subscriptions = [
        (g.merchant, g.monthly_amount)
        for g in await recurring_repo.active_for_plan(session, user.id)
        if g.category_id in cats and cats[g.category_id].name == "Subscriptions"
    ]
    merchants = [
        MerchantStat(m, a, n)
        for m, a, n, _ in await analytics_repo.top_merchants(session, user.id, month, end, None, 10)
    ]
    cards = build_insights(
        MonthFacts(
            spend_by_category=spend,
            history_by_category=history,
            history_months=len(months),
            names=names,
            income=income,
            spending=spending,
            savings_target_pct=target_pct,
            fixed_spend=fixed,
            subscriptions=subscriptions,
            merchants=merchants,
        )
    )
    return InsightsOut(
        month=month,
        insights=[
            InsightOut(
                kind=c.kind,
                title=c.title,
                body=c.body,
                impact=c.impact.quantize(Decimal("1")),
                tone=c.tone,
                category_id=c.category_id,
            )
            for c in cards
        ],
    )
