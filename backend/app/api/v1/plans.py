import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.plan import (
    EventIn,
    GenerateIn,
    PlanItemIn,
    PlanItemUpdate,
    PlanOut,
    PlanSummaryOut,
    PlanUpdate,
    ReviewOut,
    TrackingOut,
)
from app.services import planner_service, review_service, tracking_service

router = APIRouter(prefix="/plans", tags=["plans"])

MonthParam = Annotated[str, Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")]


@router.post("/generate", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def generate(
    month: MonthParam, user: CurrentUser, db: SessionDep, data: GenerateIn | None = None
) -> PlanOut:
    """Create the month's draft plan, or refresh it (your own edits are kept)."""
    return await planner_service.generate(
        db, user, planner_service.parse_month(month), data or GenerateIn()
    )


@router.get("", response_model=list[PlanSummaryOut])
async def list_plans(
    user: CurrentUser,
    db: SessionDep,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> list[PlanSummaryOut]:
    parsed = planner_service.parse_month(month) if month else None
    plans = await planner_service.list_plans(db, user, parsed)
    return [PlanSummaryOut.model_validate(p) for p in plans]


@router.get("/current/tracking", response_model=TrackingOut)
async def current_tracking(
    user: CurrentUser,
    db: SessionDep,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> TrackingOut:
    parsed: date | None = planner_service.parse_month(month) if month else None
    return await tracking_service.tracking(db, user, parsed)


@router.get("/{plan_id}", response_model=PlanOut)
async def get_plan(plan_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> PlanOut:
    return await planner_service.get_plan(db, user, plan_id)


@router.get("/{plan_id}/review", response_model=ReviewOut)
async def review(plan_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> ReviewOut:
    """Month-end review: planned vs actual, savings hit or missed."""
    return await review_service.review(db, user, plan_id)


@router.patch("/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: uuid.UUID, data: PlanUpdate, user: CurrentUser, db: SessionDep
) -> PlanOut:
    return await planner_service.update_plan(db, user, plan_id, data)


@router.post("/{plan_id}/items", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    plan_id: uuid.UUID, data: PlanItemIn, user: CurrentUser, db: SessionDep
) -> PlanOut:
    return await planner_service.add_item(db, user, plan_id, data)


@router.patch("/{plan_id}/items/{item_id}", response_model=PlanOut)
async def update_item(
    plan_id: uuid.UUID, item_id: uuid.UUID, data: PlanItemUpdate, user: CurrentUser, db: SessionDep
) -> PlanOut:
    return await planner_service.update_item(db, user, plan_id, item_id, data.planned_amount)


@router.delete("/{plan_id}/items/{item_id}", response_model=PlanOut)
async def delete_item(
    plan_id: uuid.UUID, item_id: uuid.UUID, user: CurrentUser, db: SessionDep
) -> PlanOut:
    return await planner_service.delete_item(db, user, plan_id, item_id)


@router.post("/{plan_id}/apply-suggestions", response_model=PlanOut)
async def apply_suggestions(plan_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> PlanOut:
    return await planner_service.apply_suggestions(db, user, plan_id)


@router.post("/{plan_id}/events", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def add_event(
    plan_id: uuid.UUID, data: EventIn, user: CurrentUser, db: SessionDep
) -> PlanOut:
    return await planner_service.add_event(db, user, plan_id, data)


@router.delete("/{plan_id}/events/{event_id}", response_model=PlanOut)
async def delete_event(
    plan_id: uuid.UUID, event_id: uuid.UUID, user: CurrentUser, db: SessionDep
) -> PlanOut:
    return await planner_service.delete_event(db, user, plan_id, event_id)


@router.post("/{plan_id}/activate", response_model=PlanOut)
async def activate(plan_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> PlanOut:
    return await planner_service.activate(db, user, plan_id)
