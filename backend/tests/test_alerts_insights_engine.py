import uuid
from datetime import date
from decimal import Decimal

from app.engine.alerts import (
    BudgetLine,
    ExpectedIncome,
    RecurringCharge,
    Spend,
    anomaly_alerts,
    budget_alerts,
    income_missing_alerts,
    recurring_change_alerts,
    stale_data_alert,
)
from app.engine.insights import MerchantStat, MonthFacts, build
from app.engine.money import inr

FOOD, SHOP, RENT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
NAMES = {FOOD: "Food & Dining", SHOP: "Shopping", RENT: "Rent", None: "Uncategorized"}


def D(v: str) -> Decimal:  # noqa: N802
    return Decimal(v)


def test_inr_uses_indian_grouping() -> None:
    assert inr(D("123456.4")) == "₹1,23,456"
    assert inr(D("999")) == "₹999"
    assert inr(D("-1500")) == "-₹1,500"


def test_budget_alerts() -> None:
    lines = [
        BudgetLine(FOOD, "Food & Dining", D("5000"), D("4100"), D("8200"), True),
        BudgetLine(SHOP, "Shopping", D("3000"), D("3640"), None, False),
        BudgetLine(RENT, "Rent", D("9000"), D("2000"), None, False),
        BudgetLine(None, "Uncategorized", D("0"), D("500"), None, False),  # unplanned: no alert
    ]
    alerts = [(a.type, a.message) for a in budget_alerts(lines, days_left=12)]
    assert alerts == [
        ("budget_80", "Food & Dining is at 82% with 12 days left"),
        ("pace", "At this pace, Food & Dining ends ₹3,200 over"),
        ("budget_100", "Shopping is ₹640 over budget"),
    ]
    # Past months: no "days left"
    assert budget_alerts(lines[:1], None)[0].message == "Food & Dining is at 82%"


def test_anomaly_needs_history_and_three_times_median() -> None:
    history = {SHOP: [D("999"), D("1299"), D("1500")], FOOD: [D("400")]}
    spends = [
        Spend("Croma", D("6499"), SHOP),
        Spend("Myntra", D("4000"), SHOP),  # also > 3× but smaller: only the biggest alerts
        Spend("Zomato", D("5000"), FOOD),  # too little history
    ]
    [alert] = anomaly_alerts(spends, history, NAMES)
    assert alert.message == "₹6,499 at Croma is unusual for Shopping"
    assert alert.category_id == SHOP


def test_recurring_change() -> None:
    charges = [
        RecurringCharge("Netflix", None, D("199"), D("249")),
        RecurringCharge("Spotify", None, D("119"), D("119")),
        RecurringCharge("Gym", None, D("999"), None),
    ]
    assert [a.message for a in recurring_change_alerts(charges)] == [
        "Netflix went from ₹199 to ₹249"
    ]


def test_income_missing_after_five_day_grace() -> None:
    expected = [ExpectedIncome("State University (Stipend)", None, 1)]
    assert income_missing_alerts(expected, set(), date(2026, 11, 6)) == []
    [a] = income_missing_alerts(expected, set(), date(2026, 11, 7))
    assert a.message == "State University (Stipend) hasn't arrived yet this month"
    assert income_missing_alerts(expected, {"State University (Stipend)"}, date(2026, 11, 20)) == []


def test_stale_data() -> None:
    assert stale_data_alert(date(2026, 11, 1), date(2026, 11, 10)) == []
    assert stale_data_alert(date(2026, 11, 1), date(2026, 11, 11))[0].type == "stale_data"
    assert stale_data_alert(None, date(2026, 11, 11))[0].type == "stale_data"


def _facts(**over: object) -> MonthFacts:
    base: dict[str, object] = {
        "spend_by_category": {FOOD: D("4200"), SHOP: D("400"), RENT: D("9000")},
        "history_by_category": {
            FOOD: [D("2000"), D("2100"), D("1900")],
            SHOP: [D("2000"), D("1800")],
        },
        "history_months": 3,
        "names": NAMES,
        "income": D("30000"),
        "spending": D("13600"),
        "savings_target_pct": D("20"),
        "fixed_spend": D("9000"),
        "subscriptions": [("Netflix", D("649")), ("Spotify", D("119")), ("Hotstar", D("299"))],
        "merchants": [MerchantStat("Swiggy", D("2400"), 9)],
    }
    base.update(over)
    return MonthFacts(**base)  # type: ignore[arg-type]


def test_insights_ranked_by_impact_and_capped() -> None:
    cards = build(_facts())
    assert 3 <= len(cards) <= 5
    impacts = [c.impact for c in cards]
    assert impacts == sorted(impacts, reverse=True)
    kinds = [c.kind for c in cards]
    assert kinds[0] == "savings"  # kept 16,400 vs a 6,000 target
    spike = next(c for c in cards if c.kind == "spike")
    assert spike.body == "₹4,200 this month — 2.1× your usual ₹2,000."
    assert spike.tone == "bad"
    drop = next(c for c in cards if c.kind == "drop")
    assert drop.category_id == SHOP


def test_insights_shortfall_heavy_fixed_and_subscriptions() -> None:
    cards = build(
        _facts(income=D("12000"), spending=D("13600"), fixed_spend=D("9000"), merchants=[])
    )
    by_kind = {c.kind: c for c in cards}
    assert by_kind["savings"].tone == "bad"
    assert "short of your 20% target" in by_kind["savings"].body
    assert by_kind["fixed_share"].body.startswith("Rent, EMIs and bills took 75%")


def test_new_spend_and_one_card_per_category() -> None:
    cards = build(
        _facts(
            spend_by_category={SHOP: D("1299")},
            history_by_category={},
            spending=D("1299"),
            fixed_spend=D("0"),
            subscriptions=[],
            merchants=[],
        )
    )
    shop_cards = [c for c in cards if c.category_id == SHOP]
    assert len(shop_cards) == 1  # "new spend" and "biggest" don't both appear
