import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedBase
from app.models.enums import Bucket, str_enum


class Category(TimestampedBase):
    __tablename__ = "categories"

    # NULL user_id = system default category shared by everyone.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    bucket: Mapped[Bucket] = mapped_column(str_enum(Bucket, "bucket"), nullable=False)
    icon: Mapped[str] = mapped_column(String(40), nullable=False, default="circle")
    color: Mapped[str] = mapped_column(String(9), nullable=False, default="#94a3b8")

    @property
    def is_system(self) -> bool:
        return self.user_id is None
