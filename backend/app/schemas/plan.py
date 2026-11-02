import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import Bucket, Frequency, PlanItemSource, PlanStatus, RecurringStatus
from app.schemas.analytics import InsightOut
from app.schemas.common import MoneyOut, ORMModel


class RecurringOut(ORMModel):
    id: uuid.UUID
    merchant: str
    category_id: uuid.UUID | None
    typical_amount: MoneyOut
    monthly_amount: MoneyOut
    typical_day: int
    frequency: Frequency
    active: bool
    status: RecurringStatus
    last_date: date | None
    occurrences: int


class RecurringListOut(BaseModel):
    groups: list[RecurringOut]
    monthly_total: MoneyOut  # active, not dismissed


class RecurringUpdate(BaseModel):
    status: RecurringStatus


class GenerateIn(BaseModel):
    expected_income: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)
    savings_target_pct: Decimal | None = Field(None, ge=0, le=90, decimal_places=2)


class PlanUpdate(BaseModel):
    expected_income: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)
    savings_target: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)


class PlanItemIn(BaseModel):
    category_id: uuid.UUID
    planned_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class PlanItemUpdate(BaseModel):
    planned_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class PlanItemOut(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID
    planned_amount: MoneyOut
    bucket: Bucket
    source: PlanItemSource
    basis: str


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category_id: uuid.UUID | None = None
    expected_date: date | None = None


class EventOut(ORMModel):
    id: uuid.UUID
    title: str
    amount: MoneyOut
    category_id: uuid.UUID | None
    expected_date: date | None


class CutOut(BaseModel):
    item_id: uuid.UUID
    category_id: uuid.UUID
    current: MoneyOut
    suggested: MoneyOut
    cut: MoneyOut


class FitOut(BaseModel):
    spendable: MoneyOut
    fixed_total: MoneyOut
    variable_total: MoneyOut
    discretionary_total: MoneyOut
    events_total: MoneyOut
    planned_total: MoneyOut
    gap: MoneyOut  # > 0 over budget, < 0 surplus
    status: Literal["balanced", "surplus", "over_fixable", "over_unfixable"]
    cuts: list[CutOut]
    gap_after_cuts: MoneyOut


class PlanOut(BaseModel):
    id: uuid.UUID
    month: date
    status: PlanStatus
    expected_income: MoneyOut
    income_basis: str
    income_custom: bool
    savings_target: MoneyOut
    savings_pct: Decimal | None
    savings_custom: bool
    items: list[PlanItemOut]
    events: list[EventOut]
    fit: FitOut


class PlanSummaryOut(ORMModel):
    id: uuid.UUID
    month: date
    status: PlanStatus
    expected_income: MoneyOut
    savings_target: MoneyOut


class TrackingRow(BaseModel):
    category_id: uuid.UUID | None
    bucket: Bucket
    planned: MoneyOut
    spent: MoneyOut
    remaining: MoneyOut
    pct_used: Decimal | None  # None when nothing was planned
    status: Literal["on_track", "warning", "over"]
    projected: MoneyOut | None  # month-end spend at the current pace (variable/discretionary)
    pace_warning: bool


class TrackingOut(BaseModel):
    plan_id: uuid.UUID
    month: date
    status: PlanStatus
    expected_income: MoneyOut
    actual_income: MoneyOut
    savings_target: MoneyOut
    planned_total: MoneyOut
    spent_total: MoneyOut
    remaining_total: MoneyOut
    days_in_month: int
    days_elapsed: int
    days_left: int  # including today
    flexible_planned: MoneyOut  # variable + discretionary lines
    flexible_spent: MoneyOut
    safe_to_spend: MoneyOut | None  # per day; None once the month is over
    rows: list[TrackingRow]


class PlannedActual(BaseModel):
    planned: MoneyOut
    actual: MoneyOut


class ReviewCategory(BaseModel):
    category_id: uuid.UUID | None
    bucket: Bucket
    planned: MoneyOut
    actual: MoneyOut
    diff: MoneyOut  # planned - actual: positive = under budget
    label: Literal["over", "under", "on_target", "unplanned"]


class ReviewOut(BaseModel):
    plan_id: uuid.UUID
    month: date
    status: PlanStatus
    next_month: str  # YYYY-MM
    income: PlannedActual
    spending: PlannedActual
    savings: PlannedActual
    savings_hit: bool
    savings_diff: MoneyOut  # actual - target
    categories: list[ReviewCategory]
    overspends: list[ReviewCategory]
    wins: list[ReviewCategory]
    insights: list[InsightOut]
