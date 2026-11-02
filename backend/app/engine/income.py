"""Classify credits as income, refund, cashback, self-transfer or unknown."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.engine.transfers import OwnIdentity, is_card_bill_payment, is_self_transfer
from app.models.enums import TxnKind

_REFUND = re.compile(r"\b(refund|refunded|reversal|reversed|rev|chargeback)\b", re.IGNORECASE)
_CASHBACK = re.compile(r"\b(cashback|cash back|reward|rewards|cb)\b", re.IGNORECASE)
_STIPEND = re.compile(r"\bstipend\b", re.IGNORECASE)
_SALARY = re.compile(r"\b(salary|sal|payroll|wages)\b", re.IGNORECASE)
_INTEREST = re.compile(
    r"\b(int\.? ?pd|int\.? ?cr|interest|sb int|int credit|credit interest)\b", re.IGNORECASE
)
_BANK_TRANSFER = re.compile(r"\b(neft|imps|rtgs)\b", re.IGNORECASE)

# Category names (from the seed) the classifier points at.
SALARY = "Salary"
STIPEND = "Stipend"
INTEREST = "Interest"
OTHER_INCOME = "Other Income"
REFUND_CATEGORY = "Refund"
SELF_TRANSFER_CATEGORY = "Self Transfer"


@dataclass(frozen=True)
class PastTxn:
    txn_date: date
    amount: Decimal
    merchant: str


@dataclass(frozen=True)
class CreditClassification:
    kind: TxnKind
    category_name: str


def _matches_recent_debit(
    merchant: str, amount: Decimal, on: date, debits: Iterable[PastTxn]
) -> bool:
    if not merchant:
        return False
    window_start = on - timedelta(days=30)
    return any(
        d.merchant.lower() == merchant.lower()
        and d.amount == amount
        and window_start <= d.txn_date <= on
        for d in debits
    )


def _monthly_from_same_sender(merchant: str, on: date, credits: Iterable[PastTxn]) -> bool:
    """Same sender credited in a different month within +/-3 days of the same day-of-month."""
    if not merchant:
        return False
    for c in credits:
        if c.merchant.lower() != merchant.lower():
            continue
        if (c.txn_date.year, c.txn_date.month) == (on.year, on.month):
            continue
        if abs(c.txn_date.day - on.day) <= 3 or abs(c.txn_date.day - on.day) >= 27:
            return True
    return False


def classify_credit(
    *,
    text: str,
    merchant: str,
    amount: Decimal,
    txn_date: date,
    identity: OwnIdentity,
    recent_debits: Iterable[PastTxn] = (),
    past_credits: Iterable[PastTxn] = (),
) -> CreditClassification:
    # A card bill payment shows up as a credit on the card statement; it's not income.
    if is_self_transfer(text, identity) or is_card_bill_payment(text):
        return CreditClassification(TxnKind.SELF_TRANSFER, SELF_TRANSFER_CATEGORY)
    if _REFUND.search(text) or _matches_recent_debit(merchant, amount, txn_date, recent_debits):
        return CreditClassification(TxnKind.REFUND, REFUND_CATEGORY)
    if _CASHBACK.search(text):
        return CreditClassification(TxnKind.CASHBACK, REFUND_CATEGORY)
    if _STIPEND.search(text):
        return CreditClassification(TxnKind.INCOME, STIPEND)
    if _SALARY.search(text):
        return CreditClassification(TxnKind.INCOME, SALARY)
    if _BANK_TRANSFER.search(text) and _monthly_from_same_sender(merchant, txn_date, past_credits):
        return CreditClassification(TxnKind.INCOME, SALARY)
    if _INTEREST.search(text):
        return CreditClassification(TxnKind.INCOME, INTEREST)
    return CreditClassification(TxnKind.UNKNOWN, OTHER_INCOME)
