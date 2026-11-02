import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import CategorizedBy, Direction, TxnKind
from app.schemas.common import MoneyIn, MoneyOut, ORMModel


class TransactionOut(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID
    upload_id: uuid.UUID | None
    txn_date: date
    txn_time: time | None
    amount: MoneyOut
    direction: Direction
    raw_description: str
    merchant: str
    category_id: uuid.UUID | None
    kind: TxnKind
    is_recurring: bool
    categorized_by: CategorizedBy
    note: str | None
    upi_ref: str | None
    dedup_of: uuid.UUID | None  # set when this row is a copy of a payment counted elsewhere
    ml_model_version: str | None
    created_at: datetime


class TransactionCreate(BaseModel):
    """Manual entry: cash spends and cash income."""

    txn_date: date
    amount: MoneyIn
    direction: Direction
    merchant: str = Field(min_length=1, max_length=160)
    account_id: uuid.UUID | None = None  # defaults to the user's Cash account
    category_id: uuid.UUID | None = None
    kind: TxnKind | None = None
    note: str | None = Field(None, max_length=1000)


class TransactionUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    kind: TxnKind | None = None
    note: str | None = Field(None, max_length=1000)
    apply_to_merchant: bool = False

    @model_validator(mode="after")
    def _apply_needs_category(self) -> "TransactionUpdate":
        if self.apply_to_merchant and self.category_id is None:
            raise ValueError("apply_to_merchant needs a category_id")
        return self


class TransactionUpdateOut(BaseModel):
    transaction: TransactionOut
    recategorized: int = 0  # other rows moved by apply_to_merchant


class TransactionFilters(BaseModel):
    start: date | None = None
    end: date | None = None
    category_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    kind: TxnKind | None = None
    direction: Direction | None = None
    merchant: str | None = None
    search: str | None = Field(None, max_length=120)
    min_amount: Decimal | None = Field(None, ge=0)
    max_amount: Decimal | None = Field(None, ge=0)


class PayeeStats(BaseModel):
    """What you've paid this payee before — a memory jog for "who was this?"."""

    count: int
    min_amount: MoneyOut
    max_amount: MoneyOut
    median_amount: MoneyOut
    first_date: date
    last_date: date
    usual_time: Literal["morning", "afternoon", "evening", "night"] | None


class ReviewQueueOut(BaseModel):
    uncategorized: list[TransactionOut]
    unknown_credits: list[TransactionOut]
    total: int
    payee_stats: dict[str, PayeeStats]  # keyed by merchant


class BulkCategorizeIn(BaseModel):
    transaction_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    category_id: uuid.UUID


class BulkCategorizeOut(BaseModel):
    updated: int
