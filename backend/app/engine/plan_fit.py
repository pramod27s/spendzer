"""Does the plan fit inside what's left after savings? If not, where can it give?"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from typing import Literal

from app.models.enums import Bucket, PlanItemSource

ZERO = Decimal("0")
# Cuts never take a category below this share of its forecast. Fixed costs are never cut.
CUT_FLOORS: tuple[tuple[Bucket, Decimal], ...] = (
    (Bucket.DISCRETIONARY, Decimal("0.5")),
    (Bucket.VARIABLE, Decimal("0.8")),
)

FitStatus = Literal["balanced", "surplus", "over_fixable", "over_unfixable"]


@dataclass(frozen=True)
class FitItem:
    item_id: uuid.UUID
    category_id: uuid.UUID
    bucket: Bucket
    source: PlanItemSource
    amount: Decimal


@dataclass(frozen=True)
class Cut:
    item_id: uuid.UUID
    category_id: uuid.UUID
    current: Decimal
    suggested: Decimal

    @property
    def amount(self) -> Decimal:
        return self.current - self.suggested


@dataclass
class FitResult:
    spendable: Decimal
    fixed_total: Decimal
    variable_total: Decimal
    discretionary_total: Decimal
    events_total: Decimal
    planned_total: Decimal
    gap: Decimal  # > 0 over budget, < 0 surplus
    status: FitStatus
    cuts: list[Cut] = field(default_factory=list)
    gap_after_cuts: Decimal = ZERO


def _floor_rupee(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_DOWN)


def fit(items: list[FitItem], events_total: Decimal, spendable: Decimal) -> FitResult:
    def total(pred: Callable[[FitItem], bool]) -> Decimal:
        return sum((i.amount for i in items if pred(i)), ZERO)

    fixed = total(lambda i: i.source == PlanItemSource.FIXED or i.bucket == Bucket.FIXED)
    variable = total(lambda i: i.source != PlanItemSource.FIXED and i.bucket == Bucket.VARIABLE)
    discretionary = total(
        lambda i: (
            i.source != PlanItemSource.FIXED and i.bucket not in (Bucket.FIXED, Bucket.VARIABLE)
        )
    )
    planned = fixed + variable + discretionary + events_total
    gap = planned - spendable

    result = FitResult(
        spendable=spendable,
        fixed_total=fixed,
        variable_total=variable,
        discretionary_total=discretionary,
        events_total=events_total,
        planned_total=planned,
        gap=gap,
        status="surplus" if gap < 0 else "balanced",
    )
    if gap <= 0:
        return result

    # Over budget: suggest cuts to forecast lines (never to fixed costs or the user's own
    # numbers) — discretionary first, largest first, then variable.
    remaining = gap
    for bucket, floor in CUT_FLOORS:
        lines = sorted(
            (i for i in items if i.source == PlanItemSource.FORECAST and i.bucket == bucket),
            key=lambda i: i.amount,
            reverse=True,
        )
        for line in lines:
            if remaining <= 0:
                break
            room = _floor_rupee(line.amount * (1 - floor))
            take = min(room, remaining)
            if take > 0:
                result.cuts.append(
                    Cut(line.item_id, line.category_id, line.amount, line.amount - take)
                )
                remaining -= take
    result.gap_after_cuts = remaining
    result.status = "over_fixable" if remaining <= 0 else "over_unfixable"
    return result
