import uuid
from datetime import date
from decimal import Decimal

from app.engine.forecast import forecast, median_income
from app.engine.plan_fit import FitItem, fit
from app.models.enums import Bucket, PlanItemSource

OCT, SEP, AUG = date(2026, 10, 1), date(2026, 9, 1), date(2026, 8, 1)
MONTHS = [OCT, SEP, AUG]  # newest first


def D(v: str) -> Decimal:  # noqa: N802
    return Decimal(v)


def test_forecast_median_when_every_month_has_spend() -> None:
    f = forecast([D("1070"), D("380"), D("1070")], MONTHS)
    assert f.amount == D("1070")
    assert f.basis == "Median of Aug–Oct"


def test_forecast_weighted_mean_when_a_month_is_zero() -> None:
    # 0.5 * 780 + 0.3 * 0 + 0.2 * 0
    f = forecast([D("780"), D("0"), D("0")], MONTHS)
    assert f.amount == D("390")
    assert "Weighted average" in f.basis


def test_forecast_ignores_single_outlier_month() -> None:
    f = forecast([D("1000"), D("9000"), D("1200")], MONTHS)  # Sept had a one-off splurge
    assert f.amount == D("1100")  # median of the other two
    assert "ignoring Sep" in f.basis


def test_forecast_outlier_is_judged_against_the_other_two() -> None:
    # Aug (6000) > 2 × median(100, 5000) = 5100, so Aug is the outlier.
    f = forecast([D("100"), D("5000"), D("6000")], MONTHS)
    assert f.amount == D("2550")
    assert "ignoring Aug" in f.basis


def test_forecast_short_history_and_income() -> None:
    assert forecast([], []).amount == 0
    assert forecast([D("600"), D("0")], [OCT, SEP]).amount == D("375")  # 0.5/0.8 * 600
    assert median_income([D("30000"), D("30112"), D("30000")], MONTHS).amount == D("30000")


def _item(amount: str, bucket: Bucket, source: PlanItemSource = PlanItemSource.FORECAST) -> FitItem:
    return FitItem(uuid.uuid4(), uuid.uuid4(), bucket, source, D(amount))


SPEC_ITEMS = [
    # The worked example from the spec: income 30,000, savings 6,000, spendable 24,000.
    _item("9000", Bucket.FIXED, PlanItemSource.FIXED),
    _item("299", Bucket.FIXED, PlanItemSource.FIXED),
    _item("650", Bucket.FIXED, PlanItemSource.FIXED),
    _item("3000", Bucket.VARIABLE),
    _item("2200", Bucket.VARIABLE),
    _item("5800", Bucket.DISCRETIONARY),
    _item("3000", Bucket.DISCRETIONARY),
]


def test_spec_worked_example_gap_fixed_by_cuts() -> None:
    r = fit(SPEC_ITEMS, D("1500"), D("24000"))
    assert r.fixed_total == D("9949")
    assert r.planned_total == D("25449")
    assert r.gap == D("1449")
    assert r.status == "over_fixable"
    assert sum(c.amount for c in r.cuts) == D("1449")
    # Largest discretionary line gives first, and fixed costs are never touched.
    assert r.cuts[0].current == D("5800")
    assert all(c.current not in (D("9000"), D("299"), D("650")) for c in r.cuts)
    assert r.gap_after_cuts == 0


def test_cuts_respect_floors_and_report_what_cannot_be_fixed() -> None:
    items = [
        _item("10000", Bucket.FIXED, PlanItemSource.FIXED),
        _item("2000", Bucket.DISCRETIONARY),  # can give 1000 (50% floor)
        _item("1000", Bucket.VARIABLE),  # can give 200 (80% floor)
        _item("4000", Bucket.DISCRETIONARY, PlanItemSource.USER),  # user's own number: untouched
    ]
    r = fit(items, D("0"), D("15000"))
    assert r.gap == D("2000")
    assert r.status == "over_unfixable"
    assert [(c.current, c.suggested) for c in r.cuts] == [
        (D("2000"), D("1000")),
        (D("1000"), D("800")),
    ]
    assert r.gap_after_cuts == D("800")


def test_surplus_and_balanced() -> None:
    assert fit([_item("1000", Bucket.VARIABLE)], D("0"), D("5000")).status == "surplus"
    assert fit([_item("5000", Bucket.VARIABLE)], D("0"), D("5000")).status == "balanced"
