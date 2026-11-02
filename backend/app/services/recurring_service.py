"""Recurring detection and own-account transfer pairing, run after every upload."""

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.errors import NotFoundError
from app.engine.dedup import TRANSFER_WINDOW_DAYS, Movement, pair_self_transfers
from app.engine.recurring import Debit, detect, is_active
from app.models import RecurringGroup, User
from app.models.enums import Direction, RecurringStatus, TxnKind
from app.repositories import category_repo, recurring_repo, transaction_repo
from app.schemas.plan import RecurringListOut, RecurringOut
from app.services import dedup_service

log = logging.getLogger(__name__)


async def refresh_recurring(session: AsyncSession, user: User, today: date | None = None) -> None:
    """Re-detect recurring charges. Dismissed groups stay dismissed; confirmed ones are kept."""
    today = today or clock.today()
    rows = await transaction_repo.expense_debits(session, user.id)
    candidates = detect((Debit(*r) for r in rows), today)
    groups = {g.merchant: g for g in await recurring_repo.list_for_user(session, user.id)}

    await recurring_repo.clear_transaction_links(session, user.id)
    seen: set[str] = set()
    for c in candidates:
        group = groups.get(c.merchant)
        if group is not None and group.status == RecurringStatus.DISMISSED:
            continue
        if group is None:
            group = RecurringGroup(user_id=user.id, merchant=c.merchant)
            session.add(group)
        group.category_id = c.category_id
        group.typical_amount = c.typical_amount
        group.typical_day = c.typical_day
        group.frequency = c.frequency
        group.active = c.active
        group.last_date = c.last_date
        group.occurrences = len(c.txn_ids)
        await session.flush()
        await recurring_repo.link_transactions(session, user.id, group.id, c.txn_ids)
        seen.add(c.merchant)

    for merchant, group in groups.items():
        if merchant in seen:
            continue
        if group.status == RecurringStatus.DETECTED:
            await session.delete(group)  # the pattern broke; it was only ever a guess
        elif group.last_date is not None:
            group.active = is_active(group.frequency, group.last_date, today)


async def pair_transfers(session: AsyncSession, user: User, start: date, end: date) -> int:
    """Mark matching debit/credit pairs across the user's own accounts as self-transfers."""
    pad = timedelta(days=TRANSFER_WINDOW_DAYS)
    rows = await transaction_repo.transfer_candidates(session, user.id, start - pad, end + pad)
    moves = [Movement(r.id, r.account_id, r.txn_date, r.amount, r.direction) for r in rows]
    pairs = pair_self_transfers(
        (m for m in moves if m.direction == Direction.DEBIT),
        [m for m in moves if m.direction == Direction.CREDIT],
    )
    if not pairs:
        return 0
    category = await category_repo.get_system_by_name(session, "Self Transfer")
    ids = [i for pair in pairs for i in pair]
    await transaction_repo.mark_kind(
        session, user.id, ids, TxnKind.SELF_TRANSFER, category.id if category else None
    )
    return len(pairs)


async def after_upload(session: AsyncSession, user: User, start: date, end: date) -> None:
    """Upload post-processing. Failures are logged, never fail the upload itself."""
    try:
        await dedup_service.dedupe(session, user, start, end)
        await pair_transfers(session, user, start, end)
        await refresh_recurring(session, user)
        await session.commit()
    except Exception:
        log.exception("post-processing failed user=%s", user.id)
        await session.rollback()


def _out(group: RecurringGroup) -> RecurringOut:
    return RecurringOut.model_validate(group)


async def list_recurring(session: AsyncSession, user: User) -> RecurringListOut:
    groups = await recurring_repo.list_for_user(session, user.id)
    total = sum(
        (g.monthly_amount for g in groups if g.active and g.status != RecurringStatus.DISMISSED),
        Decimal("0"),
    )
    return RecurringListOut(groups=[_out(g) for g in groups], monthly_total=total)


async def set_status(
    session: AsyncSession, user: User, group_id: uuid.UUID, status: RecurringStatus
) -> RecurringOut:
    group = await recurring_repo.get(session, user.id, group_id)
    if group is None:
        raise NotFoundError("Recurring charge")
    group.status = status
    if status == RecurringStatus.DISMISSED:
        # Its payments go back to being ordinary spending (and get forecast as such).
        await recurring_repo.clear_group_links(session, user.id, group.id)
    else:
        await refresh_recurring(session, user)
    await session.commit()
    await session.refresh(group)
    return _out(group)
