import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.engine.dedup import Movement, pair_self_transfers
from app.engine.recurring import Debit, detect, is_active
from app.models.enums import Direction, Frequency

RENT = uuid.uuid4()
TODAY = date(2026, 11, 1)


def _debits(merchant: str, dates: list[date], amounts: list[str]) -> list[Debit]:
    return [
        Debit(uuid.uuid4(), merchant, d, Decimal(a), RENT)
        for d, a in zip(dates, amounts, strict=True)
    ]


def test_monthly_charge_detected_with_typical_amount_and_day() -> None:
    rows = _debits(
        "Ramesh Kumar", [date(2026, 8, 5), date(2026, 9, 5), date(2026, 10, 6)], ["9000"] * 3
    )
    [c] = detect(rows, TODAY)
    assert c.frequency == Frequency.MONTHLY
    assert c.typical_amount == Decimal("9000.00")
    assert c.typical_day == 5
    assert c.active
    assert len(c.txn_ids) == 3
    assert c.category_id == RENT


def test_weekly_charge_detected() -> None:
    start = date(2026, 10, 2)  # a Friday
    rows = _debits("Gym Pass", [start + timedelta(days=7 * i) for i in range(4)], ["300"] * 4)
    [c] = detect(rows, date(2026, 10, 25))
    assert c.frequency == Frequency.WEEKLY
    assert c.typical_day == 4  # Friday


def test_amounts_within_ten_percent_and_one_off_extras_ignored() -> None:
    dates = [date(2026, 8, 3), date(2026, 9, 3), date(2026, 10, 3), date(2026, 10, 18)]
    rows = _debits(
        "Bajaj Finance", dates, ["2500", "2600", "2450", "15000"]
    )  # last is a prepayment
    [c] = detect(rows, TODAY)
    assert len(c.txn_ids) == 3
    assert c.typical_amount == Decimal("2500.00")


def test_not_recurring_when_amounts_vary_too_much() -> None:
    dates = [date(2026, 8, 2), date(2026, 9, 2), date(2026, 10, 2)]
    assert detect(_debits("Swiggy", dates, ["450", "380", "900"]), TODAY) == []


def test_not_recurring_when_irregular_or_too_few() -> None:
    irregular = [date(2026, 8, 2), date(2026, 8, 20), date(2026, 10, 2)]
    assert detect(_debits("Uber", irregular, ["200"] * 3), TODAY) == []
    assert (
        detect(_debits("Netflix", [date(2026, 9, 12), date(2026, 10, 12)], ["649"] * 2), TODAY)
        == []
    )


def test_inactive_when_next_charge_ten_days_overdue() -> None:
    assert is_active(Frequency.MONTHLY, date(2026, 10, 5), date(2026, 11, 13))
    assert not is_active(Frequency.MONTHLY, date(2026, 10, 5), date(2026, 11, 14))
    rows = _debits("Old Gym", [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)], ["999"] * 3)
    [c] = detect(rows, TODAY)
    assert not c.active


def test_pair_self_transfers_matches_closest_across_accounts() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    debit = Movement(uuid.uuid4(), a, date(2026, 10, 15), Decimal("5000"), Direction.DEBIT)
    near = Movement(uuid.uuid4(), b, date(2026, 10, 16), Decimal("5000"), Direction.CREDIT)
    far = Movement(uuid.uuid4(), b, date(2026, 10, 17), Decimal("5000"), Direction.CREDIT)
    same_account = Movement(uuid.uuid4(), a, date(2026, 10, 15), Decimal("5000"), Direction.CREDIT)
    assert pair_self_transfers([debit], [far, near, same_account]) == [(debit.id, near.id)]


def test_pair_requires_same_amount_and_window() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    debit = Movement(uuid.uuid4(), a, date(2026, 10, 15), Decimal("5000"), Direction.DEBIT)
    off_amount = Movement(uuid.uuid4(), b, date(2026, 10, 15), Decimal("4999"), Direction.CREDIT)
    too_late = Movement(uuid.uuid4(), b, date(2026, 10, 18), Decimal("5000"), Direction.CREDIT)
    assert pair_self_transfers([debit], [off_amount, too_late]) == []
