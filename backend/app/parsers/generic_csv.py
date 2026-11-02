"""Column-mapping parser for any bank's CSV / Excel export.

The user maps columns once per account; the mapping is stored on the account and reused.
"""

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar, Literal

from app.models.enums import Direction
from app.parsers.base import BaseParser, MappingRequired, ParsedTransaction, ParseError
from app.parsers.normalize import is_balance_row, parse_amount, parse_date, parse_direction
from app.parsers.tabular import Row, cell_text, read_rows, sniff_format

AmountMode = Literal["split", "signed", "type"]

_HEADER_HINTS: dict[str, tuple[str, ...]] = {
    "date": ("txn date", "transaction date", "tran date", "date", "value date", "posting date"),
    "description": (
        "narration",
        "description",
        "particulars",
        "transaction details",
        "details",
        "remarks",
        "transaction remarks",
    ),
    "debit": (
        "withdrawal amt",
        "withdrawal amount",
        "withdrawal",
        "debit amount",
        "debit",
        "dr amount",
        "paid out",
        "dr",
    ),
    "credit": (
        "deposit amt",
        "deposit amount",
        "deposit",
        "credit amount",
        "credit",
        "cr amount",
        "paid in",
        "cr",
    ),
    "amount": ("transaction amount", "txn amount", "amount (inr)", "amount(inr)", "amount", "amt"),
    "type": ("dr/cr", "cr/dr", "dr / cr", "debit/credit", "transaction type", "txn type", "type"),
}
_ALL_HINTS = {h for hints in _HEADER_HINTS.values() for h in hints}


def _norm_header(value: Any) -> str:
    text = cell_text(value).lower()
    text = re.sub(r"[.₹]", "", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class ColumnMapping:
    date_col: str
    description_col: str
    amount_mode: AmountMode
    debit_col: str | None = None
    credit_col: str | None = None
    amount_col: str | None = None
    type_col: str | None = None

    def validate(self) -> None:
        needed: dict[AmountMode, tuple[str, ...]] = {
            "split": ("debit_col", "credit_col"),
            "signed": ("amount_col",),
            "type": ("amount_col", "type_col"),
        }
        missing = [f for f in needed[self.amount_mode] if not getattr(self, f)]
        if missing:
            raise ParseError("INVALID_MAPPING", f"Mapping is missing: {', '.join(missing)}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColumnMapping":
        return cls(
            date_col=str(data["date_col"]),
            description_col=str(data["description_col"]),
            amount_mode=data["amount_mode"],
            debit_col=data.get("debit_col"),
            credit_col=data.get("credit_col"),
            amount_col=data.get("amount_col"),
            type_col=data.get("type_col"),
        )


def find_header_row(rows: list[Row], scan: int = 40) -> int:
    for idx, row in enumerate(rows[:scan]):
        cells = [_norm_header(c) for c in row]
        hits = sum(1 for c in cells if c in _ALL_HINTS)
        if hits >= 2:
            return idx
    return 0


def header_names(row: Row) -> list[str]:
    names: list[str] = []
    for i, value in enumerate(row):
        name = cell_text(value) or f"Column {i + 1}"
        while name in names:
            name = f"{name} ({i + 1})"
        names.append(name)
    return names


def suggest_mapping(columns: list[str]) -> dict[str, Any]:
    normalized = {_norm_header(c): c for c in columns}

    def pick(field: str, exclude: set[str]) -> str | None:
        for hint in _HEADER_HINTS[field]:
            col = normalized.get(hint)
            if col and col not in exclude:
                return col
        for hint in _HEADER_HINTS[field]:  # looser: header contains the hint word
            if len(hint) < 4:
                continue
            for norm, col in normalized.items():
                if hint in norm and col not in exclude:
                    return col
        return None

    used: set[str] = set()
    out: dict[str, Any] = {}
    for field in ("date", "description", "debit", "credit", "amount", "type"):
        col = pick(field, used)
        out[f"{field}_col"] = col
        if col:
            used.add(col)

    if out["debit_col"] and out["credit_col"]:
        out["amount_mode"] = "split"
    elif out["amount_col"] and out["type_col"]:
        out["amount_mode"] = "type"
    else:
        out["amount_mode"] = "signed"
    return out


def build_preview(file_bytes: bytes) -> dict[str, Any]:
    rows = read_rows(file_bytes)
    if not rows:
        raise ParseError("EMPTY_FILE", "The file has no rows.")
    header_idx = find_header_row(rows)
    columns = header_names(rows[header_idx])
    sample = [
        [cell_text(c) for c in row[: len(columns)]] for row in rows[header_idx + 1 : header_idx + 6]
    ]
    return {
        "columns": columns,
        "sample_rows": sample,
        "suggested_mapping": suggest_mapping(columns),
    }


class GenericCsvParser(BaseParser):
    source_type: ClassVar[str] = "generic_csv"
    label: ClassVar[str] = "Any bank (CSV / Excel)"
    extensions: ClassVar[frozenset[str]] = frozenset({".csv", ".xlsx", ".xls"})

    def __init__(self, mapping: ColumnMapping | None = None) -> None:
        self.mapping = mapping

    def can_parse(self, file_bytes: bytes, filename: str) -> bool:
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        return f".{ext}" in self.extensions and sniff_format(file_bytes) != "pdf"

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        if self.mapping is None:
            raise MappingRequired(build_preview(file_bytes))
        mapping = self.mapping
        mapping.validate()

        rows = read_rows(file_bytes)
        if not rows:
            raise ParseError("EMPTY_FILE", "The file has no rows.")
        header_idx = find_header_row(rows)
        columns = header_names(rows[header_idx])

        def col(name: str | None) -> int | None:
            if name is None:
                return None
            if name not in columns:
                raise ParseError(
                    "COLUMN_NOT_FOUND",
                    f"Column '{name}' isn't in this file. Check the column mapping.",
                )
            return columns.index(name)

        i_date, i_desc = col(mapping.date_col), col(mapping.description_col)
        i_debit, i_credit = col(mapping.debit_col), col(mapping.credit_col)
        i_amount, i_type = col(mapping.amount_col), col(mapping.type_col)

        def cell(row: Row, i: int | None) -> Any:
            return row[i] if i is not None and i < len(row) else None

        out: list[ParsedTransaction] = []
        for row in rows[header_idx + 1 :]:
            txn_date: date | None = parse_date(cell(row, i_date))
            description = cell_text(cell(row, i_desc))
            amount_dir = self._amount(row, cell, i_debit, i_credit, i_amount, i_type)

            if txn_date is None or amount_dir is None:
                # Wrapped narration line: no date, no amount -> belongs to the previous row.
                if txn_date is None and amount_dir is None and description and out:
                    prev = out[-1]
                    out[-1] = ParsedTransaction(
                        prev.txn_date,
                        prev.amount,
                        prev.direction,
                        f"{prev.raw_description} {description}",
                        prev.balance,
                    )
                continue
            if is_balance_row(description):
                continue
            amount, direction = amount_dir
            out.append(ParsedTransaction(txn_date, amount, direction, description))

        if not out:
            raise ParseError(
                "NO_TRANSACTIONS",
                "No transactions found. Check the date and amount columns in the mapping.",
            )
        return out

    def _amount(
        self,
        row: Row,
        cell: Callable[[Row, int | None], Any],
        i_debit: int | None,
        i_credit: int | None,
        i_amount: int | None,
        i_type: int | None,
    ) -> tuple[Decimal, Direction] | None:
        mode = self.mapping.amount_mode if self.mapping else "signed"
        if mode == "split":
            debit = parse_amount(cell(row, i_debit))
            if debit is not None:
                return debit[0], Direction.DEBIT
            credit = parse_amount(cell(row, i_credit))
            if credit is not None:
                return credit[0], Direction.CREDIT
            return None
        parsed = parse_amount(cell(row, i_amount))
        if parsed is None:
            return None
        amount, hint = parsed
        if mode == "type":
            direction = parse_direction(cell(row, i_type)) or hint
            return (amount, direction) if direction else None
        return amount, hint or Direction.CREDIT
