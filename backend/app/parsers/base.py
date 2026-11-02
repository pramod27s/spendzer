from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Any, ClassVar

from app.models.enums import Direction


@dataclass(frozen=True)
class ParsedTransaction:
    txn_date: date
    amount: Decimal  # always positive
    direction: Direction
    raw_description: str
    balance: Decimal | None = None
    upi_ref: str | None = None  # UPI reference / RRN when the source prints one
    merchant: str | None = None  # clean payee name when the source gives one (UPI apps)
    txn_time: time | None = None  # time of day, when the source prints it


class ParseError(Exception):
    """Parsing failed; `code` is stored on the upload and shown to the user."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MappingRequired(Exception):  # noqa: N818 - control-flow signal, not an error
    """Generic parser needs the user to map columns first."""

    def __init__(self, preview: dict[str, Any]) -> None:
        super().__init__("Column mapping required")
        self.preview = preview


class BaseParser(ABC):
    source_type: ClassVar[str]
    label: ClassVar[str]
    extensions: ClassVar[frozenset[str]]
    group: ClassVar[str] = "bank"  # bank | card | upi — for the source picker

    @abstractmethod
    def can_parse(self, file_bytes: bytes, filename: str) -> bool: ...

    @abstractmethod
    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]: ...
