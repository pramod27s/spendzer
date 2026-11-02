import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL.match(value) or len(value) > 320:
        raise ValueError("Enter a valid email address")
    return value


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)

    _email = field_validator("email")(_clean_email)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name is required")
        return v


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    _email = field_validator("email")(_clean_email)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    name: str
    monthly_savings_target_pct: Decimal
    created_at: datetime


class AuthOut(TokenOut):
    user: UserOut


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    monthly_savings_target_pct: Decimal | None = Field(None, ge=0, le=90, decimal_places=2)
