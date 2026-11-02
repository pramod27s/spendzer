"""Date and amount parsing for Indian statement formats."""

import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.enums import Direction

_DATE_FORMATS = (
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d.%m.%Y",
    "%d.%m.%y",
    "%d %b %Y",
    "%d %b %y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %B %Y",
    "%d/%b/%Y",
    "%b %d, %Y",
    "%d %b, %Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
)


def parse_date(value: Any) -> date | None:
    """Parse a statement date. Day-first always (Indian convention)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    # Drop a trailing time component: "01/11/2026 10:42:01", "2026-11-01T10:42:00"
    text = re.split(r"[ T]\d{1,2}:\d{2}", text, maxsplit=1)[0].strip()
    text = re.sub(r"\s+", " ", text)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


_AMOUNT_CLEAN = re.compile(r"[₹,\s]|INR|Rs\.?", re.IGNORECASE)


def parse_amount(value: Any) -> tuple[Decimal, Direction | None] | None:
    """Return (positive amount, direction hint) or None when the cell holds no amount.

    The hint comes from a Dr/Cr suffix or a sign: negative / (x) / Dr -> debit; Cr -> credit.
    """
    if value is None:
        return None
    if isinstance(value, int | float | Decimal) and not isinstance(value, bool):
        if isinstance(value, float) and value != value:  # NaN
            return None
        num = Decimal(str(value))
        if num == 0:
            return None
        return abs(num), (Direction.DEBIT if num < 0 else None)

    text = str(value).strip()
    if not text or text in {"-", "--"} or text.lower() in {"nan", "none"}:
        return None

    hint: Direction | None = None
    suffix = re.search(r"\b(dr|cr)\.?\s*$", text, re.IGNORECASE)
    if suffix:
        hint = Direction.DEBIT if suffix.group(1).lower() == "dr" else Direction.CREDIT
        text = text[: suffix.start()]

    text = _AMOUNT_CLEAN.sub("", text)
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    if text.startswith("-"):
        negative, text = True, text[1:]
    elif text.startswith("+"):
        text = text[1:]
    if text.endswith("-"):  # some banks print "500.00-"
        negative, text = True, text[:-1]

    try:
        num = Decimal(text)
    except InvalidOperation:
        return None
    if num == 0:
        return None
    if negative and hint is None:
        hint = Direction.DEBIT
    return num.quantize(Decimal("0.01")), hint


def parse_direction(value: Any) -> Direction | None:
    text = str(value or "").strip().lower()
    if text in {"dr", "debit", "d", "withdrawal", "debited", "paid", "sent", "w"}:
        return Direction.DEBIT
    if text in {"cr", "credit", "c", "deposit", "credited", "received", "refund"}:
        return Direction.CREDIT
    return None


_SKIP_ROW = re.compile(
    r"^\s*(opening balance|closing balance|balance b/?f|balance c/?f|brought forward|"
    r"carried forward|statement summary)\b|^\s*(grand )?totals?\s*:?\s*$",
    re.IGNORECASE,
)


def is_balance_row(description: str) -> bool:
    return bool(_SKIP_ROW.search(description))


_TIME_FORMATS = ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S", "%I:%M:%S %p")


def parse_time(value: Any) -> time | None:
    """'07:23 pm', '10:42 AM', '20:14' -> time; anything else -> None."""
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    text = " ".join(str(value or "").split()).upper()
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None
