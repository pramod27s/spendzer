import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import UploadStatus
from app.schemas.common import ORMModel


class UploadPreview(BaseModel):
    columns: list[str]
    sample_rows: list[list[str]]
    suggested_mapping: dict[str, Any]


class UploadOut(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID
    source_type: str
    file_name: str
    status: UploadStatus
    error: str | None
    txn_count: int
    period_start: date | None
    period_end: date | None
    preview: UploadPreview | None
    created_at: datetime


class ColumnMappingIn(BaseModel):
    date_col: str = Field(min_length=1)
    description_col: str = Field(min_length=1)
    amount_mode: Literal["split", "signed", "type"]
    debit_col: str | None = None
    credit_col: str | None = None
    amount_col: str | None = None
    type_col: str | None = None

    @model_validator(mode="after")
    def _check_mode(self) -> "ColumnMappingIn":
        required = {
            "split": ("debit_col", "credit_col"),
            "signed": ("amount_col",),
            "type": ("amount_col", "type_col"),
        }[self.amount_mode]
        missing = [f for f in required if not getattr(self, f)]
        if missing:
            raise ValueError(f"{self.amount_mode} mode needs: {', '.join(missing)}")
        return self


class SourceOut(BaseModel):
    source_type: str
    label: str
    group: str  # bank | card | upi
    extensions: list[str]
    needs_column_mapping: bool
    accepts_password: bool
