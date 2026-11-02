"""Per-category spending forecast from the last three months with data."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

ZERO = Decimal("0")
# Newest month first.
WEIGHTS = (Decimal("0.5"), Decimal("0.3"), Decimal("0.2"))


@dataclass(frozen=True)
class Forecast:
    amount: Decimal
    basis: str  # plain-language explanation for the UI tooltip


def month_label(months: list[date]) -> str:
    """'Aug–Oct' for a run of months (given oldest first)."""
    if not months:
        return ""
    first, last = months[0].strftime("%b"), months[-1].strftime("%b")
    return first if first == last else f"{first}–{last}"


def _rupees(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def forecast(totals: list[Decimal], months: list[date]) -> Forecast:
    """Forecast next month's spend in one category.

    `totals[i]` is the spend in `months[i]`, newest month first (up to three).
    Median normally; a 0.5/0.3/0.2 weighted mean when any month is zero; a month more than
    twice the median of the others is treated as an outlier and ignored.
    """
    if not totals:
        return Forecast(ZERO, "No recent spending")
    span = month_label(sorted(months))
    kept = list(range(len(totals)))
    ignored: list[int] = []

    if len(totals) >= 3:
        for i in range(len(totals)):
            others = [totals[j] for j in range(len(totals)) if j != i]
            base = Decimal(str(median(others)))
            if base > 0 and totals[i] > 2 * base:
                ignored.append(i)
        if len(ignored) == 1:
            kept = [i for i in kept if i not in ignored]
        else:
            ignored = []  # more than one "outlier" means there's no stable baseline

    values = [totals[i] for i in kept]
    note = ""
    if ignored:
        note = f", ignoring {months[ignored[0]].strftime('%b')} (unusually high)"

    if any(v == 0 for v in values):
        weights = [WEIGHTS[i] for i in kept]
        amount = sum((v * w for v, w in zip(values, weights, strict=True)), ZERO) / sum(weights)
        return Forecast(
            _rupees(amount), f"Weighted average of {span}{note} (some months had no spend)"
        )
    return Forecast(_rupees(Decimal(str(median(values)))), f"Median of {span}{note}")


def median_income(totals: list[Decimal], months: list[date]) -> Forecast:
    if not totals:
        return Forecast(ZERO, "")
    return Forecast(
        _rupees(Decimal(str(median(totals)))), f"Median income of {month_label(sorted(months))}"
    )
