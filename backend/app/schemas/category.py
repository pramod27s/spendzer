import uuid

from pydantic import BaseModel, Field

from app.models.enums import Bucket, MatchType
from app.schemas.common import ORMModel

_HEX = r"^#[0-9a-fA-F]{6}$"


class CategoryOut(ORMModel):
    id: uuid.UUID
    name: str
    bucket: Bucket
    icon: str
    color: str
    is_system: bool


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    bucket: Bucket
    icon: str = Field("circle", max_length=40)
    color: str = Field("#898781", pattern=_HEX)


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    bucket: Bucket | None = None
    icon: str | None = Field(None, max_length=40)
    color: str | None = Field(None, pattern=_HEX)


class MerchantRuleIn(BaseModel):
    pattern: str = Field(min_length=1, max_length=255)
    match_type: MatchType = MatchType.CONTAINS
    category_id: uuid.UUID
    priority: int = Field(10, ge=0, le=1000)


class MerchantRuleOut(ORMModel):
    id: uuid.UUID
    pattern: str
    match_type: MatchType
    category_id: uuid.UUID
    priority: int
