import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedBase, user_fk
from app.models.enums import Bucket, PlanItemSource, PlanStatus, str_enum


class MonthlyPlan(TimestampedBase):
    __tablename__ = "monthly_plans"
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_monthly_plans_user_month"),)

    user_id: Mapped[uuid.UUID] = user_fk()
    month: Mapped[date] = mapped_column(Date, nullable=False)  # first day of month
    expected_income: Mapped[Decimal] = mapped_column(nullable=False)
    savings_target: Mapped[Decimal] = mapped_column(nullable=False)
    status: Mapped[PlanStatus] = mapped_column(
        str_enum(PlanStatus, "plan_status"), nullable=False, default=PlanStatus.DRAFT
    )
    # Where expected income came from ("Median of Aug–Oct"), shown in the UI tooltip.
    income_basis: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # User-entered values survive regeneration; history-derived ones are recomputed.
    income_custom: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    savings_custom: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class PlanItem(TimestampedBase):
    __tablename__ = "plan_items"
    __table_args__ = (
        UniqueConstraint("plan_id", "category_id", "source", name="uq_plan_items_plan_cat_source"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monthly_plans.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    planned_amount: Mapped[Decimal] = mapped_column(nullable=False)
    bucket: Mapped[Bucket] = mapped_column(str_enum(Bucket, "bucket"), nullable=False)
    source: Mapped[PlanItemSource] = mapped_column(
        str_enum(PlanItemSource, "plan_item_source"), nullable=False
    )
    basis: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")


class PlannedEvent(TimestampedBase):
    __tablename__ = "planned_events"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monthly_plans.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    expected_date: Mapped[date | None] = mapped_column(Date)
