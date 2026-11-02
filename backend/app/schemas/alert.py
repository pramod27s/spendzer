import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class AlertOut(ORMModel):
    id: uuid.UUID
    type: str
    message: str
    category_id: uuid.UUID | None
    month: date
    read: bool
    created_at: datetime


class AlertListOut(BaseModel):
    alerts: list[AlertOut]
    unread: int
