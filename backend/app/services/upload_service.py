"""Statement upload pipeline: validate -> queue -> parse -> enrich -> save -> delete raw file.

Raw bytes stay in memory. The one exception: a generic CSV with no saved column mapping is
parked in a private temp file until the user maps columns (or it expires), then deleted.
"""

import hashlib
import logging
import os
import tempfile
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import AppError, ConflictError, NotFoundError
from app.engine.enrich import Enriched, enrich
from app.engine.income import PastTxn
from app.engine.merchant import extract_merchant
from app.engine.sanitize import mask_card_numbers
from app.models import Account, Upload, User
from app.models.enums import Direction, UploadStatus
from app.parsers import registry
from app.parsers.base import BaseParser, MappingRequired, ParsedTransaction, ParseError
from app.parsers.generic_csv import ColumnMapping, GenericCsvParser
from app.parsers.pdf_tools import decrypt, upi_ref_from
from app.parsers.tabular import sniff_format
from app.repositories import account_repo, transaction_repo, upload_repo, user_repo
from app.schemas.upload import ColumnMappingIn, SourceOut
from app.services import alert_service, recurring_service
from app.services.enrichment import build_context

log = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf"}
_ALLOWED_MIME_PREFIXES = (
    "text/",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml",
    "application/pdf",
    "application/octet-stream",
    "application/csv",
)


def list_sources() -> list[SourceOut]:
    return [
        SourceOut(
            source_type=p.source_type,
            label=p.label,
            group=p.group,
            extensions=sorted(p.extensions),
            needs_column_mapping=p is GenericCsvParser,
            accepts_password=".pdf" in p.extensions,
        )
        for p in registry.available()
    ]


# ---------- temp storage for files awaiting a column mapping ----------


def _tmp_dir() -> Path:
    base = get_settings().upload_tmp_dir or tempfile.gettempdir()
    path = Path(base) / "spendzer-pending"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _pending_path(upload_id: uuid.UUID) -> Path:
    return _tmp_dir() / f"{upload_id}.bin"


def discard_pending(upload_id: uuid.UUID) -> None:
    _pending_path(upload_id).unlink(missing_ok=True)


def _purge_stale_pending() -> None:
    ttl = get_settings().pending_upload_ttl_minutes * 60
    cutoff = time.time() - ttl
    for f in _tmp_dir().glob("*.bin"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
        except OSError:
            continue


# ---------- request-time steps ----------


@dataclass(frozen=True)
class QueuedUpload:
    upload: Upload
    file_bytes: bytes


def _validate_file(filename: str, content_type: str | None, size: int) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError("UNSUPPORTED_FILE", "Upload a .csv, .xlsx, .xls or .pdf statement.")
    if content_type and not content_type.startswith(_ALLOWED_MIME_PREFIXES):
        raise AppError("UNSUPPORTED_FILE", "That file type isn't a statement we can read.")
    if size == 0:
        raise AppError("EMPTY_FILE", "The file is empty.")
    if size > get_settings().max_upload_bytes:
        raise AppError("FILE_TOO_LARGE", "Statements must be 10 MB or smaller.", 413)
    return ext


async def queue_upload(
    session: AsyncSession,
    user: User,
    *,
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
    account_id: uuid.UUID,
    source_type: str,
) -> QueuedUpload:
    _validate_file(filename, content_type, len(file_bytes))
    account = await account_repo.get(session, user.id, account_id)
    if account is None:
        raise NotFoundError("Account")
    parser_cls = registry.get(source_type)
    if not parser_cls().can_parse(file_bytes, filename):
        raise AppError("WRONG_SOURCE", f"This file doesn't look like a {parser_cls.label} file.")

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    previous = await upload_repo.get_by_hash(session, user.id, file_hash)
    if previous is not None:
        if previous.status != UploadStatus.FAILED:
            raise ConflictError("DUPLICATE_FILE", "You've already uploaded this exact file.")
        # Retrying a file that failed (e.g. wrong PDF password): replace the failed attempt.
        await upload_repo.delete(session, previous)
        await session.flush()

    upload = await upload_repo.create(
        session,
        user.id,
        account_id=account.id,
        source_type=source_type,
        file_name=os.path.basename(filename)[:255],
        file_hash=file_hash,
        status=UploadStatus.PENDING,
    )
    await session.commit()
    _purge_stale_pending()
    log.info("upload queued id=%s source=%s", upload.id, source_type)
    return QueuedUpload(upload=upload, file_bytes=file_bytes)


async def submit_column_mapping(
    session: AsyncSession, user: User, upload_id: uuid.UUID, data: ColumnMappingIn
) -> QueuedUpload:
    upload = await get_upload(session, user, upload_id)
    if upload.status != UploadStatus.NEEDS_MAPPING:
        raise AppError("MAPPING_NOT_NEEDED", "This upload isn't waiting for a column mapping.")
    path = _pending_path(upload.id)
    if not path.exists():
        upload.status = UploadStatus.FAILED
        upload.error = "UPLOAD_EXPIRED"
        upload.preview = None
        await session.commit()
        raise AppError("UPLOAD_EXPIRED", "This upload expired. Please upload the file again.", 410)
    columns = set((upload.preview or {}).get("columns", []))
    used = {v for k, v in data.model_dump().items() if k.endswith("_col") and v}
    unknown = used - columns
    if unknown:
        raise AppError("COLUMN_NOT_FOUND", f"Unknown column(s): {', '.join(sorted(unknown))}")

    account = await account_repo.get(session, user.id, upload.account_id)
    if account is None:
        raise NotFoundError("Account")
    account.column_mapping = data.model_dump()
    upload.status = UploadStatus.PENDING
    upload.error = None
    await session.commit()
    file_bytes = path.read_bytes()
    return QueuedUpload(upload=upload, file_bytes=file_bytes)


async def list_uploads(
    session: AsyncSession, user: User, *, offset: int, limit: int
) -> tuple[Sequence[Upload], int]:
    return await upload_repo.list_page(session, user.id, offset=offset, limit=limit)


async def get_upload(session: AsyncSession, user: User, upload_id: uuid.UUID) -> Upload:
    upload = await upload_repo.get(session, user.id, upload_id)
    if upload is None:
        raise NotFoundError("Upload")
    return upload


async def delete_upload(session: AsyncSession, user: User, upload_id: uuid.UUID) -> None:
    upload = await get_upload(session, user, upload_id)
    await upload_repo.delete(session, upload)  # transactions cascade
    await session.commit()
    discard_pending(upload_id)


# ---------- background processing ----------


def _make_parser(source_type: str, account: Account) -> BaseParser:
    parser_cls = registry.get(source_type)
    if parser_cls is GenericCsvParser:
        mapping = (
            ColumnMapping.from_dict(account.column_mapping) if account.column_mapping else None
        )
        return GenericCsvParser(mapping)
    return parser_cls()


async def _save(
    session: AsyncSession, user: User, upload: Upload, parsed: list[ParsedTransaction]
) -> None:
    start = min(p.txn_date for p in parsed)
    end = max(p.txn_date for p in parsed)
    ctx = await build_context(session, user, start, end)

    def run(p: ParsedTransaction) -> Enriched:
        return enrich(
            ctx,
            raw_description=p.raw_description,
            txn_date=p.txn_date,
            amount=p.amount,
            direction=p.direction,
            merchant=p.merchant,
        )

    # Debits first, so refund matching and the monthly-salary check also see this
    # statement's own rows when the credits are classified.
    results: dict[int, Enriched] = {}
    for i, p in enumerate(parsed):
        if p.direction == Direction.DEBIT:
            results[i] = run(p)
            ctx.recent_debits.append(PastTxn(p.txn_date, p.amount, results[i].merchant))
    ctx.past_credits.extend(
        PastTxn(p.txn_date, p.amount, extract_merchant(mask_card_numbers(p.raw_description)))
        for p in parsed
        if p.direction == Direction.CREDIT
    )
    for i, p in enumerate(parsed):
        if p.direction == Direction.CREDIT:
            results[i] = run(p)

    rows = [
        {
            "id": uuid.uuid4(),
            "user_id": user.id,
            "account_id": upload.account_id,
            "upload_id": upload.id,
            "txn_date": p.txn_date,
            "txn_time": p.txn_time,
            "amount": p.amount,
            "direction": p.direction,
            "raw_description": results[i].raw_description,
            "merchant": results[i].merchant,
            "category_id": results[i].category_id,
            "kind": results[i].kind,
            "categorized_by": results[i].categorized_by,
            "ml_model_version": results[i].ml_model_version,
            "upi_ref": p.upi_ref or upi_ref_from(p.raw_description),
            "is_recurring": False,
        }
        for i, p in enumerate(parsed)
    ]
    await transaction_repo.bulk_insert(session, rows)
    upload.status = UploadStatus.DONE
    upload.error = None
    upload.preview = None
    upload.txn_count = len(rows)
    upload.period_start = start
    upload.period_end = end


async def process_upload(
    user_id: uuid.UUID, upload_id: uuid.UUID, file_bytes: bytes, pdf_password: str | None = None
) -> None:
    """Background task. Uses its own DB session; never logs file contents or the password."""
    park_file = False
    async with SessionLocal() as session:
        upload = await upload_repo.get(session, user_id, upload_id)
        user = await user_repo.get(session, user_id)
        if upload is None or user is None:
            return  # deleted while queued
        account = await account_repo.get(session, user_id, upload.account_id)
        if account is None:
            return
        upload.status = UploadStatus.PARSING
        await session.commit()
        try:
            readable = (
                decrypt(file_bytes, pdf_password)
                if sniff_format(file_bytes) == "pdf"
                else file_bytes
            )
            pdf_password = None  # used once, then dropped
            parsed = _make_parser(upload.source_type, account).parse(readable)
            await _save(session, user, upload, parsed)
            await session.commit()
            log.info("upload done id=%s txns=%s", upload.id, upload.txn_count)
            if upload.period_start and upload.period_end:
                await recurring_service.after_upload(
                    session, user, upload.period_start, upload.period_end
                )
                await alert_service.refresh_months(
                    session, user, upload.period_start, upload.period_end
                )
        except MappingRequired as req:
            upload.status = UploadStatus.NEEDS_MAPPING
            upload.preview = req.preview
            await session.commit()
            park_file = True
        except ParseError as exc:
            await session.rollback()
            await _fail(session, user_id, upload_id, f"{exc.code}: {exc.message}")
        except Exception:
            log.exception("upload failed id=%s", upload_id)
            await session.rollback()
            await _fail(
                session, user_id, upload_id, "PARSE_FAILED: Something went wrong reading this file."
            )
        finally:
            if park_file:
                path = _pending_path(upload_id)
                path.write_bytes(file_bytes)
                os.chmod(path, 0o600)
            else:
                discard_pending(upload_id)


async def _fail(
    session: AsyncSession, user_id: uuid.UUID, upload_id: uuid.UUID, error: str
) -> None:
    upload = await upload_repo.get(session, user_id, upload_id)
    if upload is not None:
        upload.status = UploadStatus.FAILED
        upload.error = error[:500]
        upload.preview = None
        await session.commit()
