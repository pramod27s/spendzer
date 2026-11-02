"""Read CSV / XLSX / XLS bytes into a list of rows. Format is sniffed from the bytes."""

import csv
import io
from typing import Any

from openpyxl import load_workbook

from app.parsers.base import ParseError

Row = list[Any]

_XLSX_MAGIC = b"PK\x03\x04"
_XLS_MAGIC = b"\xd0\xcf\x11\xe0"
_MAX_ROWS = 50_000


def sniff_format(file_bytes: bytes) -> str:
    if file_bytes.startswith(_XLSX_MAGIC):
        return "xlsx"
    if file_bytes.startswith(_XLS_MAGIC):
        return "xls"
    if file_bytes.startswith(b"%PDF"):
        return "pdf"
    return "csv"


def _decode(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("UNREADABLE_FILE", "Could not read the file's text encoding.")


def _read_csv(file_bytes: bytes) -> list[Row]:
    text = _decode(file_bytes)
    if "\x00" in text:
        raise ParseError("UNREADABLE_FILE", "This doesn't look like a text CSV file.")
    sample = text[:8192]
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect)][:_MAX_ROWS]


def _read_xlsx(file_bytes: bytes) -> list[Row]:
    try:
        # keep_vba=False: macros are never loaded.
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True, keep_vba=False)
    except Exception as exc:  # openpyxl raises many types for corrupt files
        raise ParseError("UNREADABLE_FILE", "Could not open the Excel file.") from exc
    try:
        ws = wb.worksheets[0]
        rows: list[Row] = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
            if len(rows) >= _MAX_ROWS:
                break
        return rows
    finally:
        wb.close()


def _read_xls(file_bytes: bytes) -> list[Row]:
    try:
        import pandas as pd

        frame = pd.read_excel(io.BytesIO(file_bytes), header=None, engine="xlrd")
    except ImportError as exc:
        raise ParseError(
            "XLS_NOT_SUPPORTED", "Legacy .xls isn't supported yet. Save it as .xlsx or .csv."
        ) from exc
    except Exception as exc:
        raise ParseError("UNREADABLE_FILE", "Could not open the Excel file.") from exc
    return frame.astype(object).where(frame.notna(), None).values.tolist()[:_MAX_ROWS]


def read_rows(file_bytes: bytes) -> list[Row]:
    fmt = sniff_format(file_bytes)
    if fmt == "xlsx":
        rows = _read_xlsx(file_bytes)
    elif fmt == "xls":
        rows = _read_xls(file_bytes)
    elif fmt == "pdf":
        raise ParseError("WRONG_SOURCE", "This is a PDF. Pick a PDF statement source instead.")
    else:
        rows = _read_csv(file_bytes)
    # Drop fully empty rows; keep positions otherwise.
    return [r for r in rows if any(c is not None and str(c).strip() for c in r)]


def cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).split())
