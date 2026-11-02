"""UPI app exports: Google Pay's statement PDF, PhonePe's PDF or CSV/Excel, Paytm's CSV/Excel.

UPI apps name the payee cleanly ("Paid to Swiggy") and print the UPI reference, which is what
lets cross-source dedup match these rows to the same payments in a bank statement.
"""

import re
from dataclasses import replace
from typing import ClassVar

from app.engine.merchant import extract_merchant
from app.models.enums import Direction
from app.parsers.base import BaseParser, ParsedTransaction, ParseError
from app.parsers.normalize import parse_amount, parse_date, parse_time
from app.parsers.pdf_tools import text_of
from app.parsers.tabular import cell_text, read_rows, sniff_format

_PAYEE = r"(?P<what>Paid to|Sent to|Payment to|Transfer to|Received from|Money received from)"
_RUPEES = r"(?:(?:₹|Rs\.?|INR)\s?)?(?P<amount>[\d,]+(?:\.\d{1,2})?)"


def _direction(what: str) -> Direction:
    return (
        Direction.CREDIT
        if what.lower().startswith(("received", "money received"))
        else Direction.DEBIT
    )


def _payee(name: str) -> str:
    name = " ".join(name.split())
    return extract_merchant(name) or name


def _attach_ref(txns: list[ParsedTransaction], ref: str) -> None:
    if txns and txns[-1].upi_ref is None:
        last = txns[-1]
        txns[-1] = replace(last, raw_description=f"{last.raw_description} · UPI {ref}", upi_ref=ref)


# The line after a transaction in app PDFs starts with its time: "10:42 AM UPI Transaction ID…"
_LEADING_TIME = re.compile(r"^(\d{1,2}:\d{2}\s?[AaPp][Mm])\b")


def _attach_time(txns: list[ParsedTransaction], line: str) -> None:
    m = _LEADING_TIME.match(line)
    if m and txns and txns[-1].txn_time is None:
        txns[-1] = replace(txns[-1], txn_time=parse_time(m.group(1)))


def _ext(filename: str) -> str:
    return "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""


def _find_header(rows: list[list[object]], required: set[str]) -> list[str] | None:
    for i, row in enumerate(rows[:30]):
        cells = [cell_text(c).lower() for c in row]
        if required <= set(cells):
            return cells + [str(i)]  # last item carries the row index
    return None


def _upi_ref(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    # Spreadsheets drop leading zeros from numeric cells ("047712986349" -> 47712986349).
    if 9 <= len(digits) < 12:
        digits = digits.zfill(12)
    return digits if len(digits) == 12 else None


def _table_rows(
    file_bytes: bytes, label: str, ref_cols: tuple[str, ...], type_col: str | None
) -> list[ParsedTransaction]:
    """Read an app's CSV / Excel export: Date, Transaction Details ("Paid to X"), Amount, plus a
    UPI reference column and (PhonePe) a DEBIT/CREDIT column or (Paytm) signed amounts."""
    rows = read_rows(file_bytes)
    found = _find_header(rows, {"date", "transaction details", "amount"})
    if found is None:
        raise ParseError("WRONG_SOURCE", f"This doesn't look like a {label} statement export.")
    header, start = found[:-1], int(found[-1]) + 1

    def col(*names: str) -> int | None:
        for name in names:
            for i, h in enumerate(header):
                if h.startswith(name):
                    return i
        return None

    i_date, i_details, i_amount = col("date"), col("transaction details"), col("amount")
    i_ref = col(*ref_cols)
    i_type = col(type_col) if type_col else None
    i_other = col("other transaction details")
    i_time = col("time")
    out: list[ParsedTransaction] = []
    for row in rows[start:]:

        def get(i: int | None, row: list[object] = row) -> str:
            return cell_text(row[i]) if i is not None and i < len(row) else ""

        txn_date = parse_date(get(i_date))
        parsed = parse_amount(get(i_amount))
        details = get(i_details)
        if txn_date is None or parsed is None:
            continue  # preamble, footer and disclaimer lines
        amount, hint = parsed
        m = re.match(rf"^{_PAYEE}\s+(?P<name>.+)$", details, re.IGNORECASE)
        kind = get(i_type).upper()
        if kind in ("DEBIT", "CREDIT"):
            direction = Direction.DEBIT if kind == "DEBIT" else Direction.CREDIT
        elif hint is not None:
            direction = hint
        else:
            direction = _direction(m.group("what")) if m else Direction.CREDIT
        ref = _upi_ref(get(i_ref))
        out.append(
            ParsedTransaction(
                txn_date,
                amount,
                direction,
                " · ".join(p for p in (details, get(i_other), f"UPI {ref}" if ref else "") if p),
                None,
                ref,
                _payee(m.group("name")) if m else None,
                parse_time(get(i_time)),
            )
        )
    if not out:
        raise ParseError("NO_TRANSACTIONS", f"No transactions found in this {label} export.")
    return out


class _UpiPdfParser(BaseParser):
    extensions: ClassVar[frozenset[str]] = frozenset({".pdf"})
    group = "upi"
    line: ClassVar[re.Pattern[str]]
    ref: ClassVar[re.Pattern[str]]

    def can_parse(self, file_bytes: bytes, filename: str) -> bool:
        return filename.lower().endswith(".pdf") and file_bytes.startswith(b"%PDF")

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        out: list[ParsedTransaction] = []
        for raw in text_of(file_bytes).splitlines():
            line = " ".join(raw.split())
            m = self.line.search(line)
            if m:
                txn_date = parse_date(m.group("date"))
                parsed = parse_amount(m.group("amount"))
                if txn_date is None or parsed is None:
                    continue
                direction = self._direction(m)
                payee = _payee(m.group("name"))
                out.append(
                    ParsedTransaction(
                        txn_date,
                        parsed[0],
                        direction,
                        f"{m.group('what')} {m.group('name').strip()}",
                        None,
                        None,
                        payee,
                    )
                )
                continue
            _attach_time(out, line)
            ref = self.ref.search(line)
            if ref:
                _attach_ref(out, ref.group(1))
        if not out:
            raise ParseError(
                "NO_TRANSACTIONS",
                f"Couldn't find transactions in this PDF. Is it a {self.label} statement?",
            )
        return out

    def _direction(self, m: re.Match[str]) -> Direction:
        return _direction(m.group("what"))


class GPayPdfParser(_UpiPdfParser):
    source_type = "gpay_pdf"
    label = "Google Pay (statement PDF)"
    # "02 Nov, 2026 Paid to Swiggy ₹450"
    line = re.compile(
        rf"^(?P<date>\d{{1,2}} [A-Za-z]{{3}},? \d{{4}})\s+{_PAYEE}\s+(?P<name>.+?)\s+{_RUPEES}$"
    )
    # "UPI Transaction ID: 402918374651"
    ref = re.compile(r"UPI Transaction ID:?\s*(\d{12})", re.IGNORECASE)


class PhonePeParser(_UpiPdfParser):
    """PhonePe statement: the PDF or the CSV / Excel download — the format is detected."""

    source_type = "phonepe"
    label = "PhonePe (PDF, CSV or Excel)"
    extensions: ClassVar[frozenset[str]] = frozenset({".pdf", ".csv", ".xlsx", ".xls"})
    # PDF lines: "Nov 02, 2026 Paid to Swiggy DEBIT ₹450"
    line = re.compile(
        rf"^(?P<date>[A-Za-z]{{3}} \d{{1,2}}, \d{{4}})\s+{_PAYEE}\s+(?P<name>.+?)"
        rf"\s+(?P<type>DEBIT|CREDIT)\s+{_RUPEES}$"
    )
    # "UTR No. 402918374651"
    ref = re.compile(r"UTR No\.?:?\s*(\d{12})", re.IGNORECASE)

    def can_parse(self, file_bytes: bytes, filename: str) -> bool:
        if _ext(filename) == ".pdf":
            return file_bytes.startswith(b"%PDF")
        return _ext(filename) in self.extensions and sniff_format(file_bytes) != "pdf"

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        if sniff_format(file_bytes) == "pdf":
            return super().parse(file_bytes)
        return _table_rows(file_bytes, "PhonePe", ("utr",), "transaction type")

    def _direction(self, m: re.Match[str]) -> Direction:
        return Direction.CREDIT if m.group("type") == "CREDIT" else Direction.DEBIT


class PaytmParser(BaseParser):
    """Paytm 'UPI Statement' download (Excel or CSV). Amounts are signed: -450.00 / +500.00."""

    source_type = "paytm"
    label = "Paytm (Excel / CSV export)"
    extensions: ClassVar[frozenset[str]] = frozenset({".csv", ".xlsx", ".xls"})
    group = "upi"

    def can_parse(self, file_bytes: bytes, filename: str) -> bool:
        return _ext(filename) in self.extensions and sniff_format(file_bytes) != "pdf"

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        return _table_rows(file_bytes, "Paytm UPI", ("upi ref",), None)
