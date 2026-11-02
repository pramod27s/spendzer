"""Transfers between the user's own accounts, and the same payment seen in two statements."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from rapidfuzz import fuzz

from app.models.enums import Direction

TRANSFER_WINDOW_DAYS = 2


@dataclass(frozen=True)
class Movement:
    id: uuid.UUID
    account_id: uuid.UUID
    txn_date: date
    amount: Decimal
    direction: Direction


def pair_self_transfers(
    debits: Iterable[Movement], credits: Iterable[Movement]
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Match a debit in account A to a credit of the same amount in account B within 2 days.

    Each transaction is used at most once; the closest dates pair first.
    """
    candidates: list[tuple[int, date, uuid.UUID, uuid.UUID]] = []
    for d in debits:
        for c in credits:
            if c.account_id == d.account_id or c.amount != d.amount:
                continue
            gap = abs((c.txn_date - d.txn_date).days)
            if gap <= TRANSFER_WINDOW_DAYS:
                candidates.append((gap, d.txn_date, d.id, c.id))

    used: set[uuid.UUID] = set()
    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    for _, _, debit_id, credit_id in sorted(candidates, key=lambda x: (x[0], x[1])):
        if debit_id in used or credit_id in used:
            continue
        used.update((debit_id, credit_id))
        pairs.append((debit_id, credit_id))
    return pairs


# ---------------------------------------------------------------- cross-source duplicates

DUP_WINDOW_DAYS = 1
MERCHANT_SIMILARITY = 80  # rapidfuzz token-set ratio, 0–100
# Lower wins: the bank or card statement is the authoritative copy of a payment.
_AUTHORITY = {"bank": 0, "card": 0, "upi": 1, "cash": 2}


@dataclass(frozen=True)
class Copy:
    id: uuid.UUID
    upload_id: uuid.UUID
    account_type: str
    direction: Direction
    amount: Decimal
    txn_date: date
    merchant: str
    upi_ref: str | None


def _same_payment(a: Copy, b: Copy) -> tuple[bool, int]:
    """(is a duplicate, match strength) — a shared UPI reference beats any name match."""
    if a.upload_id == b.upload_id or a.direction != b.direction or a.amount != b.amount:
        return False, 0
    if abs((a.txn_date - b.txn_date).days) > DUP_WINDOW_DAYS:
        return False, 0
    if a.upi_ref and b.upi_ref:
        return (a.upi_ref == b.upi_ref), 200
    score = int(fuzz.token_set_ratio(a.merchant.lower(), b.merchant.lower()))
    return score >= MERCHANT_SIMILARITY, score


def find_duplicates(rows: Iterable[Copy]) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Return (duplicate_id, kept_id) pairs. Each row is used at most once."""
    by_amount: dict[tuple[Direction, Decimal], list[Copy]] = {}
    for r in rows:
        by_amount.setdefault((r.direction, r.amount), []).append(r)

    candidates: list[tuple[int, int, Copy, Copy]] = []
    for group in by_amount.values():
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                same, strength = _same_payment(a, b)
                if same:
                    gap = abs((a.txn_date - b.txn_date).days)
                    candidates.append((-strength, gap, a, b))

    used: set[uuid.UUID] = set()
    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    for _, _, a, b in sorted(candidates, key=lambda c: (c[0], c[1])):
        if a.id in used or b.id in used:
            continue
        keep, dup = (
            (a, b)
            if _AUTHORITY.get(a.account_type, 1) <= _AUTHORITY.get(b.account_type, 1)
            else (b, a)
        )
        used.update((a.id, b.id))
        pairs.append((dup.id, keep.id))
    return pairs
