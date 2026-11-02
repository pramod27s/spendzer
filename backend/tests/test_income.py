from datetime import date
from decimal import Decimal

from app.engine.income import PastTxn, classify_credit
from app.engine.transfers import OwnIdentity, classify_debit
from app.models.enums import TxnKind

ME = OwnIdentity(user_name="Asha Verma", last4s=frozenset({"4321"}))


def _credit(
    text: str,
    merchant: str = "",
    amount: str = "1000",
    on: date = date(2026, 10, 2),
    debits: list[PastTxn] | None = None,
    credits: list[PastTxn] | None = None,
):  # noqa: ANN202
    return classify_credit(
        text=text,
        merchant=merchant,
        amount=Decimal(amount),
        txn_date=on,
        identity=ME,
        recent_debits=debits or [],
        past_credits=credits or [],
    )


def test_self_transfer_by_last4_and_name() -> None:
    assert _credit("IMPS-123-FROM A/C XXXXXX4321").kind == TxnKind.SELF_TRANSFER
    assert _credit("NEFT-SBIN-ASHA VERMA-OWN").kind == TxnKind.SELF_TRANSFER


def test_refund_by_keyword_and_by_matching_debit() -> None:
    assert _credit("UPI-AMAZON-REFUND").kind == TxnKind.REFUND
    debit = PastTxn(date(2026, 9, 20), Decimal("1299.00"), "Amazon")
    result = _credit("UPI-AMAZON-ORDER 112", "Amazon", "1299.00", debits=[debit])
    assert result.kind == TxnKind.REFUND
    # Outside the 30-day window it isn't a refund
    old = PastTxn(date(2026, 8, 1), Decimal("1299.00"), "Amazon")
    assert _credit("UPI-AMAZON-ORDER", "Amazon", "1299.00", debits=[old]).kind == TxnKind.UNKNOWN


def test_cashback() -> None:
    result = _credit("PAYTM CASHBACK")
    assert result.kind == TxnKind.CASHBACK


def test_salary_and_stipend_keywords() -> None:
    salary = _credit("NEFT-ACME TECH PVT LTD-SALARY")
    assert (salary.kind, salary.category_name) == (TxnKind.INCOME, "Salary")
    stipend = _credit("NEFT-STATE UNIVERSITY-STIPEND OCT")
    assert (stipend.kind, stipend.category_name) == (TxnKind.INCOME, "Stipend")


def test_monthly_neft_from_same_sender_is_salary() -> None:
    prior = [PastTxn(date(2026, 9, 30), Decimal("25000"), "Acme Tech")]
    result = _credit(
        "NEFT-ACMEN123456-ACME TECH PVT LTD", "Acme Tech", on=date(2026, 11, 1), credits=prior
    )
    assert (result.kind, result.category_name) == (TxnKind.INCOME, "Salary")
    # Same sender, same month doesn't count as a monthly pattern
    same_month = [PastTxn(date(2026, 11, 1), Decimal("25000"), "Acme Tech")]
    result = _credit("NEFT-ACME TECH", "Acme Tech", on=date(2026, 11, 2), credits=same_month)
    assert result.kind == TxnKind.UNKNOWN


def test_interest_and_unknown() -> None:
    assert _credit("CREDIT INTEREST CAPITALISED").category_name == "Interest"
    unknown = _credit("UPI/CR/1/KIRAN RAO/Splitwise")
    assert (unknown.kind, unknown.category_name) == (TxnKind.UNKNOWN, "Other Income")


def test_card_bill_payment_credit_is_not_income() -> None:
    assert _credit("PAYMENT RECEIVED - THANK YOU").kind == TxnKind.SELF_TRANSFER


def test_classify_debit() -> None:
    assert classify_debit("IMPS TO XXXX4321", ME) == TxnKind.SELF_TRANSFER
    assert classify_debit("CRED CLUB CREDIT CARD PAYMENT", ME) == TxnKind.SELF_TRANSFER
    assert classify_debit("ACH D- ZERODHA COIN SIP", ME) == TxnKind.INVESTMENT
    assert classify_debit("UPI/DR/1/SWIGGY", ME) == TxnKind.EXPENSE
    # Single short first names don't trigger a self-transfer match
    assert classify_debit("UPI/DR/1/ASHA", OwnIdentity(user_name="Asha")) == TxnKind.EXPENSE
