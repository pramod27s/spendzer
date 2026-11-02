import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedBase, user_fk


class Alert(TimestampedBase):
    __tablename__ = "alerts"

    user_id: Mapped[uuid.UUID] = user_fk()
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE")
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
