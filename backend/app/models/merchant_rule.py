import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedBase
from app.models.enums import MatchType, str_enum


class MerchantRule(TimestampedBase):
    __tablename__ = "merchant_rules"

    # NULL user_id = global seeded rule. User rules always beat global rules.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    match_type: Mapped[MatchType] = mapped_column(
        str_enum(MatchType, "match_type"), nullable=False, default=MatchType.CONTAINS
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
