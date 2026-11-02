"""Cross-source dedup: the same payment in a bank statement and a UPI-app export counts once."""

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.dedup import DUP_WINDOW_DAYS, Copy, find_duplicates
from app.models import User
from app.repositories import category_repo, transaction_repo


async def dedupe(session: AsyncSession, user: User, start: date, end: date) -> int:
    """Mark copies (dedup_of = kept row). Returns how many rows were marked."""
    pad = timedelta(days=DUP_WINDOW_DAYS)
    rows = await transaction_repo.dedup_candidates(session, user.id, start - pad, end + pad)
    by_id = {t.id: t for t, _ in rows}
    pairs = find_duplicates(
        Copy(t.id, t.upload_id, kind, t.direction, t.amount, t.txn_date, t.merchant, t.upi_ref)
        for t, kind in rows
        if t.upload_id is not None
    )
    if not pairs:
        return 0
    await transaction_repo.mark_duplicates(session, user.id, pairs)

    # The bank row is kept, but a UPI app often knows the payee better ("Chai Point" vs a phone
    # number). When the kept row is uncategorized and the copy isn't, borrow its answer.
    other = await category_repo.get_system_by_name(session, "Other")
    for dup_id, keep_id in pairs:
        keep, dup = by_id[keep_id], by_id[dup_id]
        keep_unsorted = keep.category_id is None or (other and keep.category_id == other.id)
        dup_sorted = dup.category_id is not None and not (other and dup.category_id == other.id)
        if keep_unsorted and dup_sorted and keep.categorized_by != "user":
            keep.category_id = dup.category_id
            keep.kind = dup.kind
            keep.merchant = dup.merchant or keep.merchant
    return len(pairs)
