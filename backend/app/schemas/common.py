from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# Money crosses the wire as a string ("1234.50") so no precision is lost in JSON.
MoneyOut = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]
MoneyIn = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(50, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
