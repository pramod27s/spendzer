import uuid
from datetime import date
from typing import Any

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedBase, user_fk
from app.models.enums import UploadStatus, str_enum


class Upload(TimestampedBase):
    __tablename__ = "uploads"
    __table_args__ = (UniqueConstraint("user_id", "file_hash", name="uq_uploads_user_file_hash"),)

    user_id: Mapped[uuid.UUID] = user_fk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[UploadStatus] = mapped_column(
        str_enum(UploadStatus, "upload_status"), nullable=False, default=UploadStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text)
    txn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    # Header names + sample rows shown in the column-mapping step (no full file contents).
    preview: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
