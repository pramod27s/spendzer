import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.engine.categorizer import Categorizer
from app.engine.dedup import Copy, find_duplicates
from app.engine.enrich import CategoryRef, EnrichContext, Enriched, enrich
from app.engine.transfers import OwnIdentity
from app.ml.model import CategoryModel, clean_text
from app.ml.train import seed_samples, train
from app.models.enums import Bucket, CategorizedBy, Direction
from app.parsers import registry
from app.parsers.base import ParsedTransaction, ParseError
from app.parsers.pdf_tools import decrypt
from tests.conftest import FIXTURES

D = Decimal
DEBIT, CREDIT = Direction.DEBIT, Direction.CREDIT


def _parse(source: str, name: str) -> list[ParsedTransaction]:
    return registry.get(source)().parse((FIXTURES / name).read_bytes())


def test_hdfc_pdf_table() -> None:
    txns = _parse("hdfc_pdf", "hdfc_statement.pdf")
    assert [(t.txn_date.day, t.amount, t.direction) for t in txns] == [
        (1, D("30000.00"), CREDIT),
        (2, D("450.00"), DEBIT),
        (4, D("9000.00"), DEBIT),
        (6, D("640.00"), DEBIT),
        (8, D("500.00"), CREDIT),
        (10, D("1299.00"), DEBIT),
    ]
    assert txns[1].upi_ref == "402918380001"
    assert txns[5].upi_ref is None  # card swipe: no UPI reference


def test_sbi_pdf_line_fallback_uses_running_balance() -> None:
    txns = _parse("sbi_pdf", "sbi_statement.pdf")
    assert [(t.amount, t.direction) for t in txns] == [
        (D("350.00"), DEBIT),
        (D("12000.00"), CREDIT),
        (D("2000.00"), DEBIT),
    ]
    assert txns[0].upi_ref == "402918381111"
    assert txns[2].raw_description.endswith("CASH WITHDRAWAL KORAMANGALA")  # wrapped line joined


def test_icici_and_card_pdfs() -> None:
    icici = _parse("icici_pdf", "icici_statement.pdf")
    assert [(t.amount, t.direction) for t in icici] == [
        (D("230.00"), DEBIT),
        (D("8000.00"), CREDIT),
    ]
    card = _parse("hdfc_card_pdf", "hdfc_card.pdf")
    assert [(t.amount, t.direction) for t in card] == [
        (D("1299.00"), DEBIT),
        (D("649.00"), DEBIT),
        (D("5000.00"), CREDIT),  # "Cr" suffix: the bill payment
    ]


def test_upi_app_exports() -> None:
    gpay = _parse("gpay_pdf", "gpay_statement.pdf")
    assert [(t.merchant, t.amount, t.direction, t.upi_ref) for t in gpay] == [
        ("Swiggy", D("450.00"), DEBIT, "402918380001"),
        ("Ramesh Kumar", D("9000.00"), DEBIT, "402918380002"),
        ("Kiran Rao", D("500.00"), CREDIT, "402918380004"),
        ("Chai Point", D("60.00"), DEBIT, "402918380009"),
    ]
    phonepe = _parse("phonepe", "phonepe_statement.pdf")
    assert [(t.merchant, t.direction, t.upi_ref) for t in phonepe] == [
        ("Blinkit", DEBIT, None),
        ("Meera Nair", CREDIT, "402918380011"),
    ]
    phonepe_csv = _parse("phonepe", "phonepe_statement.csv")
    assert [(t.merchant, t.amount, t.direction) for t in phonepe_csv] == [
        ("Ravi Kumar", D("78.00"), DEBIT),
        ("Bangalore Metro Rail Corporation", D("30.00"), DEBIT),
        ("Meera Nair", D("700.00"), CREDIT),
        ("Redbus", D("315.00"), DEBIT),
        ("Lakshmi General Stores", D("70.00"), DEBIT),
        ("Akka", D("500.00"), DEBIT),  # emoji dropped from the name
        ("Mother Dairy", D("25.00"), DEBIT),
        ("Food1", D("140.00"), DEBIT),
    ]
    assert phonepe_csv[4].upi_ref == "047712986349"  # leading zero kept
    assert all(t.upi_ref for t in phonepe_csv)
    paytm = _parse("paytm", "paytm_statement.xlsx")
    assert [(t.merchant, t.amount, t.direction, t.upi_ref) for t in paytm] == [
        ("Zomato", D("620.00"), DEBIT, "402918380012"),
        ("Kiran Rao", D("250.00"), CREDIT, "402918380013"),
    ]


def test_locked_pdf_needs_the_password() -> None:
    locked = (FIXTURES / "hdfc_statement_locked.pdf").read_bytes()
    for wrong in (None, "nope"):
        with pytest.raises(ParseError) as info:
            decrypt(locked, wrong)
        assert info.value.code == "PDF_PASSWORD_REQUIRED"
    assert len(registry.get("hdfc_pdf")().parse(decrypt(locked, "ASHA1234"))) == 6


def test_pdf_parsers_reject_other_files() -> None:
    assert not registry.get("hdfc_pdf")().can_parse(b"Date,Amount\n", "statement.csv")
    assert not registry.get("paytm")().can_parse(b"%PDF-1.4", "x.pdf")
    with pytest.raises(ParseError) as info:
        registry.get("gpay_pdf")().parse((FIXTURES / "hdfc_card.pdf").read_bytes())
    assert info.value.code == "NO_TRANSACTIONS"


# ---------------------------------------------------------------- dedup

BANK_UP, GPAY_UP = uuid.uuid4(), uuid.uuid4()


def _copy(up: uuid.UUID, kind: str, day: int, amount: str, merchant: str, ref: str | None) -> Copy:
    return Copy(uuid.uuid4(), up, kind, DEBIT, D(amount), date(2026, 11, day), merchant, ref)


def test_dedup_by_upi_reference_keeps_the_bank_row() -> None:
    upi = _copy(GPAY_UP, "upi", 2, "450", "Swiggy", "402918380001")
    bank = _copy(BANK_UP, "bank", 2, "450", "Swiggy", "402918380001")
    assert find_duplicates([upi, bank]) == [(upi.id, bank.id)]


def test_dedup_reference_mismatch_is_not_a_duplicate() -> None:
    a = _copy(GPAY_UP, "upi", 2, "450", "Swiggy", "402918380001")
    b = _copy(BANK_UP, "bank", 2, "450", "Swiggy", "402918389999")
    assert find_duplicates([a, b]) == []


def test_dedup_fuzzy_merchant_within_a_day() -> None:
    upi = _copy(GPAY_UP, "upi", 6, "640", "BLINKIT", None)
    bank = _copy(BANK_UP, "bank", 7, "640", "Blinkit", "402918380003")
    other = _copy(GPAY_UP, "upi", 6, "640", "Zepto", None)
    assert find_duplicates([upi, bank, other]) == [(upi.id, bank.id)]
    late = _copy(GPAY_UP, "upi", 9, "640", "Blinkit", None)
    assert find_duplicates([late, bank]) == []


def test_dedup_never_within_one_upload() -> None:
    a = _copy(BANK_UP, "bank", 2, "450", "Swiggy", None)
    b = _copy(BANK_UP, "bank", 2, "450", "Swiggy", None)  # two real orders
    assert find_duplicates([a, b]) == []


# ---------------------------------------------------------------- ML


@pytest.fixture(scope="module")
def model() -> CategoryModel:
    return train(seed_samples())


def test_clean_text_anonymizes() -> None:
    raw = "UPI/DR/402918374651/SWIGGY/YESB/swiggy@ybl/Payment 4591XXXXXXXX1234"
    assert clean_text("Swiggy", raw) == "swiggy swiggy yesb"


def test_model_generalizes_to_misspellings(model: CategoryModel) -> None:
    for merchant, expected in [("Dominoz Pizza", "Food & Dining"), ("Bigbasketnow", "Groceries")]:
        guess = model.predict(merchant, merchant.upper())
        assert guess is not None
        assert guess.category_name == expected
        assert guess.confidence >= 0.6


class _FakeModel:
    def __init__(self, confidence: float) -> None:
        self.confidence = confidence

    def predict(self, merchant: str, raw: str) -> SimpleNamespace:
        return SimpleNamespace(
            category_name="Food & Dining", confidence=self.confidence, version="v-test"
        )


def _run(confidence: float, food: CategoryRef, other: CategoryRef) -> Enriched:
    ctx = EnrichContext(Categorizer([]), OwnIdentity(), [food, other], ml=_FakeModel(confidence))
    return enrich(
        ctx,
        raw_description="UPI/DR/1/DOMINOZ",
        txn_date=date(2026, 11, 1),
        amount=D("300"),
        direction=DEBIT,
    )


def test_ml_layer_only_used_when_confident() -> None:
    food = CategoryRef(uuid.uuid4(), "Food & Dining", Bucket.DISCRETIONARY)
    other = CategoryRef(uuid.uuid4(), "Other", Bucket.DISCRETIONARY)
    sure = _run(0.9, food, other)
    assert (sure.category_id, sure.categorized_by, sure.ml_model_version) == (
        food.id,
        CategorizedBy.ML,
        "v-test",
    )
    unsure = _run(0.4, food, other)
    assert (unsure.category_id, unsure.categorized_by) == (other.id, CategorizedBy.RULE)


def test_model_does_not_guess_on_person_payments(model: CategoryModel) -> None:
    # Regression: "Paid to <name>" once looked like "prepaid" -> Mobile & Internet.
    for name in ("Divya", "Ravi Kumar S", "Akka", "Bhagyalakshmi", "Venkatesh R K"):
        guess = model.predict(name, f"Paid to {name.upper()} · UPI 402918390001")
        assert guess is not None
        assert guess.category_name == "Other" or guess.confidence < 0.6, (name, guess)
