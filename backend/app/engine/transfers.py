"""Narration checks for money that is not real spending: self-transfers, card bills, investments."""

import re
from dataclasses import dataclass, field

from app.models.enums import TxnKind


@dataclass(frozen=True)
class OwnIdentity:
    """What we know about the user's own accounts, used to spot self-transfers."""

    user_name: str = ""
    last4s: frozenset[str] = field(default_factory=frozenset)


_CARD_BILL = re.compile(
    r"\b(credit ?card (bill )?payment|cc ?(bill )?payment|card ?bill|cred club|"
    r"autopay ?cc|billdesk\*?cred|payment received.*thank you)\b",
    re.IGNORECASE,
)

_INVESTMENT = re.compile(
    r"\b(zerodha|groww|upstox|angel ?one|kuvera|coin by zerodha|mutual ?funds?|"
    r"sip|ppf|nps|indian clearing corp|iccl|bse star|mf utilities|cams|kfintech|"
    r"recurring deposit|fixed deposit)\b",
    re.IGNORECASE,
)


def _mentions_last4(text: str, last4: str) -> bool:
    # Masked ("XX1234", "**1234") or a full account number ending in last4.
    return bool(
        re.search(rf"[X*x]{{2,}}\d{{0,8}}{last4}\b", text)
        or re.search(rf"(?<!\d)\d{{4,14}}{last4}(?!\d)", text)
    )


def _mentions_own_name(text: str, user_name: str) -> bool:
    name = " ".join(user_name.split())
    if len(name) < 5 or " " not in name:  # single short names collide with merchants
        return False
    return re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE) is not None


def is_self_transfer(text: str, identity: OwnIdentity) -> bool:
    if any(_mentions_last4(text, l4) for l4 in identity.last4s):
        return True
    return _mentions_own_name(text, identity.user_name)


def is_card_bill_payment(text: str) -> bool:
    return _CARD_BILL.search(text) is not None


def is_investment(text: str) -> bool:
    return _INVESTMENT.search(text) is not None


def classify_debit(text: str, identity: OwnIdentity) -> TxnKind:
    """Debits are spending unless they move money to the user's own pockets."""
    if is_self_transfer(text, identity) or is_card_bill_payment(text):
        return TxnKind.SELF_TRANSFER
    if is_investment(text):
        return TxnKind.INVESTMENT
    return TxnKind.EXPENSE
