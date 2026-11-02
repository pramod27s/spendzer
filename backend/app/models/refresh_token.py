import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedBase, user_fk


class RefreshToken(TimestampedBase):
    """One row per issued refresh token (keyed by JWT jti) so tokens can rotate and be revoked."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = user_fk()
    jti: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
