"""Alert rules. Pure functions: data in, alert drafts out. The service decides what's new."""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median

from app.engine.money import inr

ANOMALY_FACTOR = Decimal("3")
ANOMALY_MIN_HISTORY = 3
RECURRING_CHANGE = Decimal("0.10")
INCOME_GRACE_DAYS = 5
STALE_DAYS = 10


@dataclass(frozen=True)
class AlertDraft:
    type: str
    message: str
    category_id: uuid.UUID | None


@dataclass(frozen=True)
class BudgetLine:
    category_id: uuid.UUID | None
    name: str
    planned: Decimal
    spent: Decimal
    projected: Decimal | None
    pace_warning: bool


def budget_alerts(lines: Iterable[BudgetLine], days_left: int | None) -> list[AlertDraft]:
    """budget_80 / budget_100 / pace. Only planned lines can cross a limit."""
    out: list[AlertDraft] = []
    for line in lines:
        if line.planned <= 0:
            continue
        if line.spent > line.planned:
            out.append(
                AlertDraft(
                    "budget_100",
                    f"{line.name} is {inr(line.spent - line.planned)} over budget",
                    line.category_id,
                )
            )
            continue
        pct = line.spent / line.planned * 100
        if pct >= 80:
            left = (
                f" with {days_left} {'day' if days_left == 1 else 'days'} left" if days_left else ""
            )
            out.append(
                AlertDraft("budget_80", f"{line.name} is at {pct:.0f}%{left}", line.category_id)
            )
        if line.pace_warning and line.projected is not None:
            out.append(
                AlertDraft(
                    "pace",
                    f"At this pace, {line.name} ends {inr(line.projected - line.planned)} over",
                    line.category_id,
                )
            )
    return out


@dataclass(frozen=True)
class Spend:
    merchant: str
    amount: Decimal
    category_id: uuid.UUID | None


def anomaly_alerts(
    month_spends: Iterable[Spend],
    history: Mapping[uuid.UUID | None, list[Decimal]],
    names: Mapping[uuid.UUID | None, str],
) -> list[AlertDraft]:
    """One alert per category: its biggest payment, if it's over 3× the category's usual."""
    biggest: dict[uuid.UUID | None, Spend] = {}
    for s in month_spends:
        past = history.get(s.category_id, [])
        if len(past) < ANOMALY_MIN_HISTORY:
            continue
        usual = Decimal(str(median(past)))
        if s.amount > usual * ANOMALY_FACTOR and (
            s.category_id not in biggest or s.amount > biggest[s.category_id].amount
        ):
            biggest[s.category_id] = s
    return [
        AlertDraft(
            "anomaly",
            f"{inr(s.amount)} at {s.merchant or 'one merchant'} is unusual for "
            f"{names.get(s.category_id, 'this category')}",
            s.category_id,
        )
        for s in biggest.values()
    ]


@dataclass(frozen=True)
class RecurringCharge:
    merchant: str
    category_id: uuid.UUID | None
    typical_amount: Decimal
    latest_amount: Decimal | None  # newest charge from this merchant in the month


def recurring_change_alerts(charges: Iterable[RecurringCharge]) -> list[AlertDraft]:
    out: list[AlertDraft] = []
    for c in charges:
        if c.latest_amount is None or c.typical_amount <= 0:
            continue
        if abs(c.latest_amount - c.typical_amount) / c.typical_amount > RECURRING_CHANGE:
            out.append(
                AlertDraft(
                    "recurring_change",
                    f"{c.merchant} went from {inr(c.typical_amount)} to {inr(c.latest_amount)}",
                    c.category_id,
                )
            )
    return out


@dataclass(frozen=True)
class ExpectedIncome:
    source: str  # merchant name of the payer
    category_id: uuid.UUID | None
    typical_day: int


def income_missing_alerts(
    expected: Iterable[ExpectedIncome], received_from: set[str], today: date
) -> list[AlertDraft]:
    return [
        AlertDraft("income_missing", f"{e.source} hasn't arrived yet this month", e.category_id)
        for e in expected
        if e.source not in received_from and today.day > e.typical_day + INCOME_GRACE_DAYS
    ]


def stale_data_alert(last_upload: date | None, today: date) -> list[AlertDraft]:
    if last_upload is not None and (today - last_upload).days < STALE_DAYS:
        return []
    return [AlertDraft("stale_data", "Upload a statement to keep tracking accurate", None)]
