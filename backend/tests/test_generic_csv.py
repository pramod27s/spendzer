import io
from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.models.enums import Direction
from app.parsers.base import MappingRequired, ParseError
from app.parsers.generic_csv import ColumnMapping, GenericCsvParser, build_preview
from tests.conftest import FIXTURES, SPLIT_MAPPING

BANK = (FIXTURES / "bank_split_columns.csv").read_bytes()
CARD = (FIXTURES / "card_signed_amounts.csv").read_bytes()


def test_preview_finds_header_below_junk_rows_and_suggests_mapping() -> None:
    preview = build_preview(BANK)
    assert preview["columns"][:2] == ["Date", "Narration"]
    suggested = preview["suggested_mapping"]
    assert suggested["date_col"] == "Date"
    assert suggested["description_col"] == "Narration"
    assert suggested["debit_col"] == "Withdrawal Amt."
    assert suggested["credit_col"] == "Deposit Amt."
    assert suggested["amount_mode"] == "split"
    assert len(preview["sample_rows"]) == 5


def test_parse_without_mapping_asks_for_one() -> None:
    with pytest.raises(MappingRequired) as info:
        GenericCsvParser().parse(BANK)
    assert "columns" in info.value.preview


def test_parse_split_columns_skips_balance_rows() -> None:
    txns = GenericCsvParser(ColumnMapping.from_dict(SPLIT_MAPPING)).parse(BANK)
    assert len(txns) == 24
    assert not any("BALANCE" in t.raw_description for t in txns)
    salary = txns[0]
    assert salary.txn_date == date(2026, 8, 1)
    assert salary.amount == Decimal("30000.00")
    assert salary.direction == Direction.CREDIT
    swiggy = txns[1]
    assert (swiggy.amount, swiggy.direction) == (Decimal("450.00"), Direction.DEBIT)


def test_parse_signed_amounts_with_dr_cr_suffixes() -> None:
    preview = build_preview(CARD)
    mapping = ColumnMapping.from_dict(preview["suggested_mapping"])
    assert mapping.amount_mode == "signed"
    txns = GenericCsvParser(mapping).parse(CARD)
    assert [(t.amount, t.direction) for t in txns] == [
        (Decimal("119.00"), Direction.DEBIT),
        (Decimal("2450.50"), Direction.DEBIT),
        (Decimal("5000.00"), Direction.CREDIT),
        (Decimal("1200.00"), Direction.DEBIT),
        (Decimal("40.00"), Direction.CREDIT),
    ]
    assert txns[0].txn_date == date(2026, 11, 2)


def _xlsx(rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_xlsx_with_type_column_and_wrapped_narration() -> None:
    data = _xlsx(
        [
            ["Txn Date", "Description", "Amount", "Dr/Cr"],
            [datetime(2026, 10, 3), "UPI/DR/1/SWIGGY", 250.0, "DR"],
            [None, "/swiggy@ybl/Order 77", None, None],  # wrapped continuation line
            ["04/10/2026", "NEFT SALARY", "20,000.00", "CR"],
        ]
    )
    preview = build_preview(data)
    assert preview["suggested_mapping"]["amount_mode"] == "type"
    txns = GenericCsvParser(ColumnMapping.from_dict(preview["suggested_mapping"])).parse(data)
    assert len(txns) == 2
    assert txns[0].raw_description == "UPI/DR/1/SWIGGY /swiggy@ybl/Order 77"
    assert (txns[0].amount, txns[0].direction) == (Decimal("250.00"), Direction.DEBIT)
    assert txns[1].direction == Direction.CREDIT


def test_missing_column_and_empty_results_raise_parse_errors() -> None:
    bad = ColumnMapping.from_dict({**SPLIT_MAPPING, "debit_col": "Nope"})
    with pytest.raises(ParseError) as info:
        GenericCsvParser(bad).parse(BANK)
    assert info.value.code == "COLUMN_NOT_FOUND"

    wrong = ColumnMapping.from_dict({**SPLIT_MAPPING, "date_col": "Narration"})
    with pytest.raises(ParseError) as info:
        GenericCsvParser(wrong).parse(BANK)
    assert info.value.code == "NO_TRANSACTIONS"


def test_can_parse_rejects_pdf_and_unknown_extensions() -> None:
    parser = GenericCsvParser()
    assert parser.can_parse(BANK, "statement.csv")
    assert not parser.can_parse(b"%PDF-1.7 ...", "statement.csv")
    assert not parser.can_parse(BANK, "statement.txt")


def test_parse_legacy_xls() -> None:
    data = (FIXTURES / "bank_legacy.xls").read_bytes()
    preview = build_preview(data)
    mapping = ColumnMapping.from_dict(preview["suggested_mapping"])
    txns = GenericCsvParser(mapping).parse(data)
    assert [(t.txn_date, t.amount, t.direction) for t in txns] == [
        (date(2026, 11, 2), Decimal("320.00"), Direction.DEBIT),
        (date(2026, 11, 3), Decimal("30000.00"), Direction.CREDIT),
        (date(2026, 11, 5), Decimal("9000.00"), Direction.DEBIT),
    ]
