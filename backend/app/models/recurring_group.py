import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedBase, user_fk
from app.models.enums import Frequency, RecurringStatus, str_enum


class RecurringGroup(TimestampedBase):
    __tablename__ = "recurring_groups"

    user_id: Mapped[uuid.UUID] = user_fk()
    merchant: Mapped[str] = mapped_column(String(160), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    typical_amount: Mapped[Decimal] = mapped_column(nullable=False)
    typical_day: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[Frequency] = mapped_column(str_enum(Frequency, "frequency"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[RecurringStatus] = mapped_column(
        str_enum(RecurringStatus, "recurring_status"),
        nullable=False,
        default=RecurringStatus.DETECTED,
        server_default=RecurringStatus.DETECTED.value,
    )
    last_date: Mapped[date | None] = mapped_column(Date)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    @property
    def monthly_amount(self) -> Decimal:
        """What this charge costs per month, whatever its rhythm."""
        if self.frequency == Frequency.WEEKLY:
            return (self.typical_amount * 52 / 12).quantize(Decimal("1"))
        if self.frequency == Frequency.YEARLY:
            return (self.typical_amount / 12).quantize(Decimal("1"))
        return self.typical_amount
