"""Bank and credit-card PDF statements.

Each bank is a set of column aliases over the shared table reader. If a statement has no ruled
table, the line fallback reads its text instead. Layouts drift over time — when a parser stops
matching, extend its aliases rather than writing a new parser.
"""

from typing import ClassVar

from app.parsers.base import BaseParser, ParsedTransaction, ParseError
from app.parsers.pdf_tools import Columns, parse_lines, parse_table, table_rows, text_of

PDF = frozenset({".pdf"})


class PdfStatementParser(BaseParser):
    extensions: ClassVar[frozenset[str]] = PDF
    columns: ClassVar[Columns]
    use_line_fallback: ClassVar[bool] = True

    def can_parse(self, file_bytes: bytes, filename: str) -> bool:
        return filename.lower().endswith(".pdf") and file_bytes.startswith(b"%PDF")

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        """`file_bytes` must already be decrypted (see pdf_tools.decrypt)."""
        txns = parse_table(table_rows(file_bytes), self.columns)
        if not txns and self.use_line_fallback:
            txns = parse_lines(text_of(file_bytes))
        if not txns:
            raise ParseError(
                "NO_TRANSACTIONS",
                f"Couldn't find transactions in this PDF. Is it a {self.label} statement?",
            )
        return txns


class HdfcPdfParser(PdfStatementParser):
    source_type = "hdfc_pdf"
    label = "HDFC Bank (PDF)"
    columns = Columns(
        date=("date", "txn date"),
        description=("narration", "description"),
        debit=("withdrawal amt", "withdrawal amount", "withdrawal"),
        credit=("deposit amt", "deposit amount", "deposit"),
        balance=("closing balance", "balance"),
        ref=("chq/refno", "refno", "ref no", "cheque no"),
    )


class SbiPdfParser(PdfStatementParser):
    source_type = "sbi_pdf"
    label = "SBI (PDF)"
    columns = Columns(
        date=("txn date", "transaction date", "date"),
        description=("description", "narration", "particulars"),
        debit=("debit", "withdrawal"),
        credit=("credit", "deposit"),
        balance=("balance",),
        ref=("ref no/cheque no", "ref no/cheque", "refno", "ref no", "cheque no"),
    )


class IciciPdfParser(PdfStatementParser):
    source_type = "icici_pdf"
    label = "ICICI Bank (PDF)"
    columns = Columns(
        date=("transaction date", "txn date", "value date", "date"),
        description=("transaction remarks", "remarks", "particulars", "description"),
        debit=("withdrawal amount inr", "withdrawal amount", "withdrawal"),
        credit=("deposit amount inr", "deposit amount", "deposit"),
        balance=("balance inr", "balance"),
        ref=("cheque number", "ref no"),
    )


class HdfcCardPdfParser(PdfStatementParser):
    source_type = "hdfc_card_pdf"
    label = "HDFC Credit Card (PDF)"
    group = "card"
    # Card statements list one amount; payments and refunds carry a "Cr" suffix.
    columns = Columns(
        date=("date", "transaction date"),
        description=("transaction description", "description", "details"),
        amount=("amount in rs", "amount inr", "amount"),
    )
    use_line_fallback = False  # without a balance column the fallback can't tell direction
