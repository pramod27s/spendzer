import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas.plan import RecurringListOut, RecurringOut, RecurringUpdate
from app.services import recurring_service

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.get("", response_model=RecurringListOut)
async def list_recurring(user: CurrentUser, db: SessionDep) -> RecurringListOut:
    return await recurring_service.list_recurring(db, user)


@router.patch("/{group_id}", response_model=RecurringOut)
async def update_recurring(
    group_id: uuid.UUID, data: RecurringUpdate, user: CurrentUser, db: SessionDep
) -> RecurringOut:
    """Confirm a detected charge, or dismiss it so it's never suggested again."""
    return await recurring_service.set_status(db, user, group_id, data.status)
