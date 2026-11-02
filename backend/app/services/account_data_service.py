"""Data rights: export everything as CSV, delete the account and every row it owns."""

import csv
import io
from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, AuthError
from app.core.security import verify_password
from app.models import Account, Category, Transaction, Upload, User
from app.services import upload_service

EXPORT_COLUMNS = [
    "date",
    "direction",
    "amount",
    "merchant",
    "category",
    "kind",
    "counted",
    "account",
    "source",
    "note",
    "upi_ref",
    "narration",
]


async def export_rows(session: AsyncSession, user: User) -> list[list[str]]:
    stmt = (
        select(Transaction, Account.name, Category.name, Upload.file_name)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .outerjoin(Upload, Upload.id == Transaction.upload_id)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.txn_date, Transaction.created_at)
    )
    rows = []
    for t, account, category, file_name in (await session.execute(stmt)).all():
        counted = t.dedup_of is None and t.kind in ("expense", "income")
        rows.append(
            [
                t.txn_date.isoformat(),
                str(t.direction),
                f"{t.amount:.2f}",
                t.merchant,
                category or "",
                str(t.kind),
                "yes" if counted else ("duplicate" if t.dedup_of else "no"),
                account,
                file_name or "manual entry",
                t.note or "",
                t.upi_ref or "",
                t.raw_description,
            ]
        )
    return rows


def to_csv(rows: list[list[str]]) -> Iterator[str]:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(EXPORT_COLUMNS)
    yield buf.getvalue()
    for row in rows:
        buf.seek(0)
        buf.truncate()
        # Neutralise spreadsheet formulas in user-controlled text (CSV injection).
        writer.writerow(
            [f"'{c}" if c[:1] in ("=", "+", "-", "@") and not _is_number(c) else c for c in row]
        )
        yield buf.getvalue()


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


async def delete_account(session: AsyncSession, user: User, password: str) -> None:
    if user.email == get_settings().demo_email:
        raise AppError("DEMO_ACCOUNT", "The shared demo account can't be deleted.", 403)
    if not verify_password(password, user.password_hash):
        raise AuthError("INVALID_CREDENTIALS", "That password isn't right.")
    pending = (await session.scalars(select(Upload.id).where(Upload.user_id == user.id))).all()
    await session.delete(user)  # every user-owned table cascades on users.id
    await session.commit()
    for upload_id in pending:
        upload_service.discard_pending(upload_id)
