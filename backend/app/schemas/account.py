import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.engine.sanitize import normalize_last4
from app.models.enums import AccountType
from app.schemas.common import ORMModel


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: AccountType
    institution: str | None = Field(None, max_length=120)
    # Users may paste a full number; only the last 4 digits are ever kept.
    last4: str | None = Field(None, max_length=32)

    _last4 = field_validator("last4")(normalize_last4)


class AccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    institution: str | None = Field(None, max_length=120)
    last4: str | None = Field(None, max_length=32)

    _last4 = field_validator("last4")(normalize_last4)


class AccountOut(ORMModel):
    id: uuid.UUID
    name: str
    type: AccountType
    institution: str | None
    last4: str | None
    has_column_mapping: bool
    created_at: datetime
