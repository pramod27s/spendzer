from datetime import date, datetime
from decimal import Decimal

import pytest

from app.engine.sanitize import mask_card_numbers, normalize_last4
from app.models.enums import Direction
from app.parsers.normalize import is_balance_row, parse_amount, parse_date, parse_direction


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("01/11/2026", date(2026, 11, 1)),
        ("01-11-26", date(2026, 11, 1)),
        ("01 Nov 2026", date(2026, 11, 1)),
        ("1 November 2026", date(2026, 11, 1)),
        ("01-Nov-2026", date(2026, 11, 1)),
        ("2026-11-01", date(2026, 11, 1)),
        ("05/11/2026 10:42:01", date(2026, 11, 5)),
        (datetime(2026, 11, 5, 9, 30), date(2026, 11, 5)),
        ("12/03/2026", date(2026, 3, 12)),  # day-first, always
        ("", None),
        ("not a date", None),
        (None, None),
    ],
)
def test_parse_date(value: object, expected: date | None) -> None:
    assert parse_date(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1,23,456.00", (Decimal("123456.00"), None)),
        ("₹ 2,450.50", (Decimal("2450.50"), None)),
        ("-119.00", (Decimal("119.00"), Direction.DEBIT)),
        ("(500.00)", (Decimal("500.00"), Direction.DEBIT)),
        ("1200.00 Dr", (Decimal("1200.00"), Direction.DEBIT)),
        ("40.00 Cr", (Decimal("40.00"), Direction.CREDIT)),
        ("500.00-", (Decimal("500.00"), Direction.DEBIT)),
        (-75.5, (Decimal("75.5"), Direction.DEBIT)),
        (250, (Decimal("250"), None)),
        ("0.00", None),
        ("", None),
        ("-", None),
        (None, None),
        (float("nan"), None),
    ],
)
def test_parse_amount(value: object, expected: tuple[Decimal, Direction | None] | None) -> None:
    assert parse_amount(value) == expected


def test_parse_direction() -> None:
    assert parse_direction("DR") == Direction.DEBIT
    assert parse_direction("Credit") == Direction.CREDIT
    assert parse_direction("??") is None


def test_balance_rows() -> None:
    assert is_balance_row("OPENING BALANCE")
    assert is_balance_row("Closing Balance as on 31/10")
    assert not is_balance_row("TOTAL GAS STATION")  # only leading "Total" rows
    assert not is_balance_row("UPI/DR/123/SWIGGY")


def test_mask_card_numbers_keeps_last4_and_upi_refs() -> None:
    assert mask_card_numbers("POS 4111111111111111 STORE") == "POS XXXXXXXXXXXX1111 STORE"
    assert mask_card_numbers("CARD 4111 1111 1111 1111") == "CARD XXXXXXXXXXXX1111"
    # 12-digit UPI reference numbers are not card numbers
    assert mask_card_numbers("UPI/DR/402918374651/SWIGGY") == "UPI/DR/402918374651/SWIGGY"
    # Non-Luhn long runs (reference ids) are untouched
    assert mask_card_numbers("REF 1234567890123") == "REF 1234567890123"


def test_normalize_last4() -> None:
    assert normalize_last4("50100123454321") == "4321"
    assert normalize_last4("XXXX-4321") == "4321"
    assert normalize_last4("12") is None
    assert normalize_last4(None) is None
