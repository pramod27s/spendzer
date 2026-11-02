"""Find subscriptions, rent and EMIs: the same merchant, a similar amount, at a steady rhythm."""

import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from app.models.enums import Frequency

MIN_OCCURRENCES = 3
AMOUNT_TOLERANCE = Decimal("0.10")
OVERDUE_DAYS = 10
_INTERVALS = {Frequency.MONTHLY: (28, 33), Frequency.WEEKLY: (6, 8)}
_PERIOD_DAYS = {Frequency.MONTHLY: 30, Frequency.WEEKLY: 7}


@dataclass(frozen=True)
class Debit:
    id: uuid.UUID
    merchant: str
    txn_date: date
    amount: Decimal
    category_id: uuid.UUID | None


@dataclass(frozen=True)
class RecurringCandidate:
    merchant: str
    category_id: uuid.UUID | None
    typical_amount: Decimal
    typical_day: int  # day of month (monthly) or weekday 0=Mon (weekly)
    frequency: Frequency
    txn_ids: tuple[uuid.UUID, ...]
    last_date: date
    active: bool


def _median_decimal(values: list[Decimal]) -> Decimal:
    return Decimal(str(median(values))).quantize(Decimal("0.01"))


def _frequency(dates: list[date]) -> Frequency | None:
    gaps = [(b - a).days for a, b in zip(dates, dates[1:], strict=False)]
    for freq, (lo, hi) in _INTERVALS.items():
        if all(lo <= g <= hi for g in gaps):
            return freq
    return None


def is_active(frequency: Frequency, last_date: date, today: date) -> bool:
    """Inactive once the expected next charge is 10+ days overdue."""
    expected = last_date + timedelta(days=_PERIOD_DAYS[frequency])
    return (today - expected).days < OVERDUE_DAYS


def detect(debits: Iterable[Debit], today: date) -> list[RecurringCandidate]:
    by_merchant: dict[str, list[Debit]] = defaultdict(list)
    for d in debits:
        if d.merchant:
            by_merchant[d.merchant].append(d)

    found: list[RecurringCandidate] = []
    for merchant, rows in by_merchant.items():
        if len(rows) < MIN_OCCURRENCES:
            continue
        mid = _median_decimal([r.amount for r in rows])
        band = mid * AMOUNT_TOLERANCE
        # Keep the charges near the typical amount; one-off extras to the same payee drop out.
        steady = sorted((r for r in rows if abs(r.amount - mid) <= band), key=lambda r: r.txn_date)
        if len(steady) < MIN_OCCURRENCES:
            continue
        freq = _frequency([r.txn_date for r in steady])
        if freq is None:
            continue

        last = steady[-1].txn_date
        if freq == Frequency.MONTHLY:
            typical_day = int(median(r.txn_date.day for r in steady))
        else:
            typical_day = Counter(r.txn_date.weekday() for r in steady).most_common(1)[0][0]
        category = Counter(r.category_id for r in steady).most_common(1)[0][0]
        found.append(
            RecurringCandidate(
                merchant=merchant,
                category_id=category,
                typical_amount=_median_decimal([r.amount for r in steady]),
                typical_day=typical_day,
                frequency=freq,
                txn_ids=tuple(r.id for r in steady),
                last_date=last,
                active=is_active(freq, last, today),
            )
        )
    return sorted(found, key=lambda c: c.merchant)
