import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedBase
from app.models.enums import CategorizedBy, Direction, TxnKind, str_enum


class Transaction(TimestampedBase):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_date", "user_id", "txn_date"),
        Index("ix_transactions_user_category", "user_id", "category_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), index=True
    )
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Time of day when the source prints one (UPI apps do; most bank statements don't).
    txn_time: Mapped[time | None] = mapped_column(Time)
    amount: Mapped[Decimal] = mapped_column(nullable=False)  # always positive
    direction: Mapped[Direction] = mapped_column(str_enum(Direction, "direction"), nullable=False)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    merchant: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    kind: Mapped[TxnKind] = mapped_column(str_enum(TxnKind, "txn_kind"), nullable=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurring_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recurring_groups.id", ondelete="SET NULL")
    )
    dedup_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL")
    )
    categorized_by: Mapped[CategorizedBy] = mapped_column(
        str_enum(CategorizedBy, "categorized_by"), nullable=False, default=CategorizedBy.RULE
    )
    note: Mapped[str | None] = mapped_column(Text)
    # 12-digit UPI reference (RRN) when the source shows one: the strongest duplicate signal.
    upi_ref: Mapped[str | None] = mapped_column(String(32), index=True)
    # Which model version categorized this row (categorized_by = "ml").
    ml_model_version: Mapped[str | None] = mapped_column(String(40))
