"""source_type -> parser class. New parsers register here."""

from app.core.errors import AppError
from app.parsers.bank_pdf import HdfcCardPdfParser, HdfcPdfParser, IciciPdfParser, SbiPdfParser
from app.parsers.base import BaseParser
from app.parsers.generic_csv import GenericCsvParser
from app.parsers.upi_apps import GPayPdfParser, PaytmParser, PhonePeParser

_PARSERS: dict[str, type[BaseParser]] = {
    p.source_type: p
    for p in (
        GenericCsvParser,
        HdfcPdfParser,
        SbiPdfParser,
        IciciPdfParser,
        HdfcCardPdfParser,
        GPayPdfParser,
        PhonePeParser,
        PaytmParser,
    )
}


def get(source_type: str) -> type[BaseParser]:
    parser = _PARSERS.get(source_type)
    if parser is None:
        raise AppError("UNKNOWN_SOURCE", f"Unsupported statement source '{source_type}'")
    return parser


def available() -> list[type[BaseParser]]:
    return list(_PARSERS.values())
