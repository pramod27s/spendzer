import uuid
from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedBase, user_fk
from app.models.enums import AccountType, str_enum


class Account(TimestampedBase):
    __tablename__ = "accounts"

    user_id: Mapped[uuid.UUID] = user_fk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[AccountType] = mapped_column(str_enum(AccountType, "account_type"), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(120))
    last4: Mapped[str | None] = mapped_column(String(4))
    # Saved generic CSV/Excel column mapping, reused for every later upload to this account.
    column_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    @property
    def has_column_mapping(self) -> bool:
        return bool(self.column_mapping)
