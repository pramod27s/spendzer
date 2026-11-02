import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core import clock
from app.core.deps import CurrentUser, SessionDep
from app.schemas.analytics import (
    CategoriesOut,
    DailyOut,
    InsightsOut,
    MerchantsOut,
    PeriodName,
    PeriodOut,
    SummaryOut,
    TrendOut,
)
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


class PeriodQuery(BaseModel):
    period: PeriodName = "this_month"
    start: date | None = None
    end: date | None = None
    account_id: uuid.UUID | None = None


Period = Annotated[PeriodQuery, Depends()]


def _resolve(q: PeriodQuery) -> tuple[PeriodOut, PeriodOut]:
    return analytics_service.resolve_period(q.period, q.start, q.end)


@router.get("/summary", response_model=SummaryOut)
async def summary(q: Period, user: CurrentUser, db: SessionDep) -> SummaryOut:
    period, previous = _resolve(q)
    return await analytics_service.summary(db, user, period, previous, q.account_id)


@router.get("/categories", response_model=CategoriesOut)
async def categories(q: Period, user: CurrentUser, db: SessionDep) -> CategoriesOut:
    period, _ = _resolve(q)
    return await analytics_service.categories(db, user, period, q.account_id)


@router.get("/trend", response_model=TrendOut)
async def trend(
    user: CurrentUser,
    db: SessionDep,
    months: Annotated[int, Query(ge=2, le=24)] = 6,
    end_month: Annotated[date | None, Query(description="Any date in the last month")] = None,
    account_id: uuid.UUID | None = None,
) -> TrendOut:
    return await analytics_service.trend(db, user, months, end_month, account_id)


@router.get("/merchants", response_model=MerchantsOut)
async def merchants(
    q: Period,
    user: CurrentUser,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> MerchantsOut:
    period, _ = _resolve(q)
    return await analytics_service.merchants(db, user, period, q.account_id, limit)


@router.get("/insights", response_model=InsightsOut)
async def insights(
    user: CurrentUser,
    db: SessionDep,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")] = None,
) -> InsightsOut:
    target = date.fromisoformat(f"{month}-01") if month else clock.today()
    return await analytics_service.insights(db, user, target)


@router.get("/daily", response_model=DailyOut)
async def daily(q: Period, user: CurrentUser, db: SessionDep) -> DailyOut:
    period, _ = _resolve(q)
    return await analytics_service.daily(db, user, period, q.account_id)
