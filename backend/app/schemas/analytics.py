import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.models.enums import Bucket
from app.schemas.common import MoneyOut

PeriodName = Literal["this_month", "last_month", "last_3", "last_6", "last_12", "custom"]


class PeriodOut(BaseModel):
    name: PeriodName
    start: date
    end: date
    label: str


class Totals(BaseModel):
    income: MoneyOut
    spending: MoneyOut
    net_savings: MoneyOut
    savings_rate: Decimal | None  # percent, 1 dp; None when there's no income


class SummaryOut(Totals):
    period: PeriodOut
    txn_count: int
    previous: Totals
    has_data: bool
    latest_txn_date: date | None  # lets the UI jump to the newest month with data


class CategorySlice(BaseModel):
    category_id: uuid.UUID | None
    name: str
    icon: str
    color: str
    bucket: Bucket
    amount: MoneyOut
    pct: Decimal
    count: int


class BucketSlice(BaseModel):
    bucket: Bucket
    amount: MoneyOut
    pct_of_spending: Decimal
    pct_of_income: Decimal | None


class CategoriesOut(BaseModel):
    period: PeriodOut
    total: MoneyOut
    income: MoneyOut
    categories: list[CategorySlice]
    buckets: list[BucketSlice]


class TrendPoint(BaseModel):
    month: str  # YYYY-MM
    income: MoneyOut
    spending: MoneyOut
    savings: MoneyOut


class TrendOut(BaseModel):
    points: list[TrendPoint]


class MerchantRow(BaseModel):
    merchant: str
    amount: MoneyOut
    count: int
    category_id: uuid.UUID | None


class MerchantsOut(BaseModel):
    period: PeriodOut
    merchants: list[MerchantRow]


class DayPoint(BaseModel):
    date: date
    amount: MoneyOut


class WeekdayPoint(BaseModel):
    weekday: int  # 0 = Monday
    label: str
    average: MoneyOut


class DailyOut(BaseModel):
    period: PeriodOut
    days: list[DayPoint]
    weekdays: list[WeekdayPoint]


class InsightOut(BaseModel):
    kind: str
    title: str
    body: str
    impact: MoneyOut
    tone: Literal["good", "bad", "neutral"]
    category_id: uuid.UUID | None


class InsightsOut(BaseModel):
    month: date
    insights: list[InsightOut]
