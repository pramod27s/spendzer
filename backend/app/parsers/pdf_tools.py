"""PDF helpers shared by bank, card and UPI-app parsers.

Decryption happens in memory with pikepdf; the password is never stored or logged.
Tables come from pdfplumber; when a statement has no ruled table, a line-regex fallback reads
the text and infers each row's direction from the running balance.
"""

import io
import re
from dataclasses import dataclass
from decimal import Decimal

import pdfplumber
import pikepdf

from app.models.enums import Direction
from app.parsers.base import ParsedTransaction, ParseError
from app.parsers.normalize import is_balance_row, parse_amount, parse_date
from app.parsers.tabular import cell_text

MAX_PAGES = 200


def decrypt(file_bytes: bytes, password: str | None) -> bytes:
    """Return an unencrypted copy of the PDF. Wrong or missing password -> PDF_PASSWORD_REQUIRED."""
    try:
        with pikepdf.open(io.BytesIO(file_bytes), password=password or "") as pdf:
            if not pdf.is_encrypted:
                return file_bytes
            out = io.BytesIO()
            pdf.save(out)
            return out.getvalue()
    except pikepdf.PasswordError as exc:
        raise ParseError(
            "PDF_PASSWORD_REQUIRED",
            "This PDF is password-protected. Enter its password and upload again.",
        ) from exc
    except pikepdf.PdfError as exc:
        raise ParseError("UNREADABLE_FILE", "Could not open the PDF.") from exc


def text_of(file_bytes: bytes, max_chars: int | None = None) -> str:
    """Plain text of the PDF (used for bank detection and line parsing)."""
    chunks: list[str] = []
    total = 0
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages[:MAX_PAGES]:
            text = page.extract_text() or ""
            chunks.append(text)
            total += len(text)
            if max_chars and total >= max_chars:
                break
    return "\n".join(chunks)


def table_rows(file_bytes: bytes) -> list[list[str]]:
    """Every table row on every page, cells flattened to single-line text."""
    rows: list[list[str]] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages[:MAX_PAGES]:
            for table in page.extract_tables():
                for row in table:
                    cells = [cell_text(c) for c in row]
                    if any(cells):
                        rows.append(cells)
    return rows


# ---------------------------------------------------------------- column-mapped tables


@dataclass(frozen=True)
class Columns:
    """Header aliases for one statement layout (lowercased, punctuation-light)."""

    date: tuple[str, ...]
    description: tuple[str, ...]
    debit: tuple[str, ...] = ()
    credit: tuple[str, ...] = ()
    amount: tuple[str, ...] = ()  # single amount column with Dr/Cr suffix or sign
    balance: tuple[str, ...] = ()
    ref: tuple[str, ...] = ()


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9/ ]", "", text.lower()).strip()


def _find(header: list[str], aliases: tuple[str, ...]) -> int | None:
    normalized = [_norm(h) for h in header]
    for alias in aliases:
        for i, h in enumerate(normalized):
            if h == alias:
                return i
    for alias in aliases:
        for i, h in enumerate(normalized):
            if alias and alias in h:
                return i
    return None


def parse_table(rows: list[list[str]], cols: Columns) -> list[ParsedTransaction]:
    """Find the header row, then read every following row. Repeated headers (one per page)
    and wrapped narration lines are handled."""
    header_idx = None
    for i, row in enumerate(rows[:80]):
        if _find(row, cols.date) is not None and _find(row, cols.description) is not None:
            header_idx = i
            break
    if header_idx is None:
        return []
    header = rows[header_idx]
    i_date, i_desc = _find(header, cols.date), _find(header, cols.description)
    i_debit, i_credit = _find(header, cols.debit), _find(header, cols.credit)
    i_amount, i_bal, i_ref = (
        _find(header, cols.amount),
        _find(header, cols.balance),
        _find(header, cols.ref),
    )
    if (
        i_date is None
        or i_desc is None
        or (i_amount is None and (i_debit is None or i_credit is None))
    ):
        return []

    def cell(row: list[str], i: int | None) -> str:
        return row[i] if i is not None and i < len(row) else ""

    out: list[ParsedTransaction] = []
    for row in rows[header_idx + 1 :]:
        if row == header:
            continue  # header repeated on the next page
        txn_date = parse_date(cell(row, i_date))
        description = cell(row, i_desc)
        if i_amount is not None:
            parsed = parse_amount(cell(row, i_amount))
            amount_dir = (parsed[0], parsed[1] or Direction.DEBIT) if parsed else None
        else:
            debit, credit = parse_amount(cell(row, i_debit)), parse_amount(cell(row, i_credit))
            amount_dir = (
                (debit[0], Direction.DEBIT)
                if debit
                else (credit[0], Direction.CREDIT)
                if credit
                else None
            )
        if txn_date is None or amount_dir is None:
            if txn_date is None and amount_dir is None and description and out:
                prev = out[-1]
                out[-1] = ParsedTransaction(
                    prev.txn_date,
                    prev.amount,
                    prev.direction,
                    f"{prev.raw_description} {description}",
                    prev.balance,
                    prev.upi_ref,
                )
            continue
        if is_balance_row(description):
            continue
        balance = parse_amount(cell(row, i_bal)) if i_bal is not None else None
        out.append(
            ParsedTransaction(
                txn_date,
                amount_dir[0],
                amount_dir[1],
                description,
                balance[0] if balance else None,
                upi_ref_from(cell(row, i_ref), description),
            )
        )
    return out


# ---------------------------------------------------------------- line fallback

_DATE = r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[ -][A-Za-z]{3}[ -,]*\d{2,4})"
_AMOUNT = r"-?[\d,]+\.\d{2}(?:\s?(?:Dr|Cr|DR|CR))?"
_LINE = re.compile(
    rf"^(?P<date>{_DATE})\s+(?P<rest>.*?)\s+(?P<amounts>{_AMOUNT}(?:\s+{_AMOUNT}){{0,2}})\s*$"
)
_LEADING_DATE = re.compile(rf"^{_DATE}\s+")
_OPENING = re.compile(rf"opening balance.*?(?P<bal>{_AMOUNT})\s*$", re.IGNORECASE)
_CREDIT_HINT = re.compile(
    r"\b(cr|credit|deposit|salary|refund|reversal|interest|received)\b|/CR/", re.I
)


def parse_lines(text: str) -> list[ParsedTransaction]:
    """Statements without ruled tables: one transaction per dated line; the last amount is the
    running balance, and the balance moving down means money went out."""
    out: list[ParsedTransaction] = []
    prev_balance: Decimal | None = None
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        opening = _OPENING.search(line)
        if opening and (bal := parse_amount(opening.group("bal"))):
            prev_balance = bal[0]
            continue
        m = _LINE.match(line)
        if not m:
            # A wrapped narration line continues the previous transaction.
            if out and not re.search(r"\d+\.\d{2}\s*$", line) and len(line) < 120:
                prev = out[-1]
                out[-1] = ParsedTransaction(
                    prev.txn_date,
                    prev.amount,
                    prev.direction,
                    f"{prev.raw_description} {line}",
                    prev.balance,
                    prev.upi_ref,
                )
            continue
        txn_date = parse_date(m.group("date"))
        if txn_date is None:
            continue
        description = _LEADING_DATE.sub("", m.group("rest"))  # drop a value-date column
        if is_balance_row(description):
            continue
        tokens = re.findall(_AMOUNT, m.group("amounts"))
        amounts = [parse_amount(t) for t in tokens]
        parsed = [a for a in amounts if a]
        if not parsed:
            continue
        amount, hint = parsed[0]
        balance = parsed[-1][0] if len(parsed) >= 2 else None
        if hint is not None:
            direction = hint
        elif balance is not None and prev_balance is not None:
            direction = Direction.DEBIT if balance < prev_balance else Direction.CREDIT
        else:
            direction = Direction.CREDIT if _CREDIT_HINT.search(description) else Direction.DEBIT
        prev_balance = balance if balance is not None else prev_balance
        out.append(
            ParsedTransaction(
                txn_date, amount, direction, description, balance, upi_ref_from("", description)
            )
        )
    return out


_RRN = re.compile(r"(?<!\d)(\d{12})(?!\d)")


def upi_ref_from(*texts: str) -> str | None:
    """A 12-digit UPI RRN from a reference cell or a UPI narration."""
    for text in texts:
        if not text:
            continue
        if "upi" in text.lower() or text.strip().isdigit():
            m = _RRN.search(text)
            if m:
                return m.group(1)
    return None
