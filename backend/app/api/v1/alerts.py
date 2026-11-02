import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.alert import AlertListOut, AlertOut
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertListOut)
async def list_alerts(
    user: CurrentUser,
    db: SessionDep,
    unread: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> AlertListOut:
    alerts, unread_count = await alert_service.list_alerts(db, user, unread, limit)
    return AlertListOut(alerts=[AlertOut.model_validate(a) for a in alerts], unread=unread_count)


@router.patch("/{alert_id}/read", response_model=AlertOut)
async def mark_read(alert_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> AlertOut:
    return AlertOut.model_validate(await alert_service.mark_read(db, user, alert_id))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(user: CurrentUser, db: SessionDep) -> Response:
    await alert_service.mark_all_read(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
