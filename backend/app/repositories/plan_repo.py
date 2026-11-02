import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MonthlyPlan, PlanItem, PlannedEvent
from app.models.enums import PlanItemSource, PlanStatus


async def get(session: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID) -> MonthlyPlan | None:
    return await session.scalar(
        select(MonthlyPlan).where(MonthlyPlan.id == plan_id, MonthlyPlan.user_id == user_id)
    )


async def get_by_month(
    session: AsyncSession, user_id: uuid.UUID, month: date
) -> MonthlyPlan | None:
    return await session.scalar(
        select(MonthlyPlan).where(MonthlyPlan.user_id == user_id, MonthlyPlan.month == month)
    )


async def list_for_user(session: AsyncSession, user_id: uuid.UUID) -> Sequence[MonthlyPlan]:
    stmt = (
        select(MonthlyPlan).where(MonthlyPlan.user_id == user_id).order_by(MonthlyPlan.month.desc())
    )
    return (await session.scalars(stmt)).all()


async def add(session: AsyncSession, plan: MonthlyPlan) -> MonthlyPlan:
    session.add(plan)
    await session.flush()
    return plan


async def items(session: AsyncSession, plan_id: uuid.UUID) -> Sequence[PlanItem]:
    stmt = (
        select(PlanItem).where(PlanItem.plan_id == plan_id).order_by(PlanItem.planned_amount.desc())
    )
    return (await session.scalars(stmt)).all()


async def get_item(
    session: AsyncSession, plan_id: uuid.UUID, item_id: uuid.UUID
) -> PlanItem | None:
    return await session.scalar(
        select(PlanItem).where(PlanItem.id == item_id, PlanItem.plan_id == plan_id)
    )


async def delete_generated_items(session: AsyncSession, plan_id: uuid.UUID) -> None:
    """Regeneration replaces fixed + forecast lines; the user's own lines stay."""
    await session.execute(
        delete(PlanItem).where(
            PlanItem.plan_id == plan_id,
            PlanItem.source.in_([PlanItemSource.FIXED, PlanItemSource.FORECAST]),
        )
    )


async def add_items(session: AsyncSession, rows: Sequence[PlanItem]) -> None:
    session.add_all(rows)
    await session.flush()


async def delete_item(session: AsyncSession, item: PlanItem) -> None:
    await session.delete(item)


async def events(session: AsyncSession, plan_id: uuid.UUID) -> Sequence[PlannedEvent]:
    stmt = (
        select(PlannedEvent)
        .where(PlannedEvent.plan_id == plan_id)
        .order_by(PlannedEvent.expected_date.nulls_last(), PlannedEvent.created_at)
    )
    return (await session.scalars(stmt)).all()


async def get_event(
    session: AsyncSession, plan_id: uuid.UUID, event_id: uuid.UUID
) -> PlannedEvent | None:
    return await session.scalar(
        select(PlannedEvent).where(PlannedEvent.id == event_id, PlannedEvent.plan_id == plan_id)
    )


async def add_event(session: AsyncSession, event: PlannedEvent) -> PlannedEvent:
    session.add(event)
    await session.flush()
    return event


async def delete_event(session: AsyncSession, event: PlannedEvent) -> None:
    await session.delete(event)


async def close_before(session: AsyncSession, user_id: uuid.UUID, month: date) -> None:
    """Active plans for months before `month` are over: mark them closed."""
    await session.execute(
        update(MonthlyPlan)
        .where(
            MonthlyPlan.user_id == user_id,
            MonthlyPlan.status == PlanStatus.ACTIVE,
            MonthlyPlan.month < month,
        )
        .values(status=PlanStatus.CLOSED)
    )
