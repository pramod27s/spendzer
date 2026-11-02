"""Insight cards: short plain-language observations, ranked by rupee impact. No LLM — each is
a template filled with the user's own numbers."""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import median
from typing import Literal

from app.engine.money import inr

ZERO = Decimal("0")
SPIKE_RATIO = Decimal("1.5")
SPIKE_MIN_EXTRA = Decimal("300")
DROP_RATIO = Decimal("0.6")
DROP_MIN_USUAL = Decimal("500")
NEW_SPEND_MIN = Decimal("500")
HABIT_MIN_COUNT = 4
MAX_CARDS = 5

Tone = Literal["good", "bad", "neutral"]


@dataclass(frozen=True)
class Insight:
    kind: str
    title: str
    body: str
    impact: Decimal
    tone: Tone
    category_id: uuid.UUID | None = None


@dataclass(frozen=True)
class MerchantStat:
    merchant: str
    amount: Decimal
    count: int


@dataclass(frozen=True)
class MonthFacts:
    """Everything the templates need about one month, plus the months before it."""

    spend_by_category: Mapping[uuid.UUID | None, Decimal]
    # Spend per category in each earlier month with data (up to 3), any order.
    history_by_category: Mapping[uuid.UUID | None, Sequence[Decimal]]
    history_months: int
    names: Mapping[uuid.UUID | None, str]
    income: Decimal
    spending: Decimal
    savings_target_pct: Decimal
    fixed_spend: Decimal
    subscriptions: Sequence[tuple[str, Decimal]]  # (merchant, monthly amount)
    merchants: Sequence[MerchantStat]


def _times(ratio: Decimal) -> str:
    return f"{ratio:.1f}×".replace(".0×", "×")


def build(f: MonthFacts) -> list[Insight]:
    cards: list[Insight] = []

    for category_id, spent in f.spend_by_category.items():
        name = f.names.get(category_id, "Uncategorized")
        past = list(f.history_by_category.get(category_id, []))
        past += [ZERO] * (f.history_months - len(past))
        if not past:
            continue
        usual = Decimal(str(median(past)))
        if usual > 0 and spent >= usual * SPIKE_RATIO and spent - usual >= SPIKE_MIN_EXTRA:
            cards.append(
                Insight(
                    "spike",
                    f"{name} is up",
                    f"{inr(spent)} this month — {_times(spent / usual)} your usual {inr(usual)}.",
                    spent - usual,
                    "bad",
                    category_id,
                )
            )
        elif usual >= DROP_MIN_USUAL and spent <= usual * DROP_RATIO:
            cards.append(
                Insight(
                    "drop",
                    f"Less on {name}",
                    f"{inr(spent)} this month against your usual {inr(usual)} — "
                    f"{inr(usual - spent)} kept.",
                    usual - spent,
                    "good",
                    category_id,
                )
            )
        elif usual == 0 and f.history_months >= 2 and spent >= NEW_SPEND_MIN:
            cards.append(
                Insight(
                    "new_spend",
                    f"New: {name}",
                    f"{inr(spent)} on {name} — nothing there in the months before.",
                    spent / 2,
                    "neutral",
                    category_id,
                )
            )

    # Categories you usually spend on but didn't touch this month.
    for category_id, past_values in f.history_by_category.items():
        if category_id in f.spend_by_category:
            continue
        past = list(past_values) + [ZERO] * (f.history_months - len(past_values))
        usual = Decimal(str(median(past))) if past else ZERO
        if usual >= DROP_MIN_USUAL:
            name = f.names.get(category_id, "Uncategorized")
            cards.append(
                Insight(
                    "drop",
                    f"Nothing on {name}",
                    f"You usually spend {inr(usual)} on {name}. Not a rupee this month.",
                    usual,
                    "good",
                    category_id,
                )
            )

    if f.income > 0:
        saved = f.income - f.spending
        rate = saved / f.income * 100
        target = f.income * f.savings_target_pct / 100
        if saved >= target:
            cards.append(
                Insight(
                    "savings",
                    "Savings goal beaten" if f.savings_target_pct > 0 else "You saved",
                    f"You kept {rate:.0f}% of your income ({inr(saved)}) — "
                    f"your target is {f.savings_target_pct:.0f}%.",
                    saved - target,
                    "good",
                )
            )
        else:
            cards.append(
                Insight(
                    "savings",
                    "Short of your savings goal",
                    f"You kept {max(rate, ZERO):.0f}% of your income — {inr(target - saved)} short "
                    f"of your {f.savings_target_pct:.0f}% target.",
                    target - saved,
                    "bad",
                )
            )
        if f.fixed_spend > f.income / 2:
            cards.append(
                Insight(
                    "fixed_share",
                    "Fixed costs are heavy",
                    f"Rent, EMIs and bills took {f.fixed_spend / f.income * 100:.0f}% "
                    f"of your income ({inr(f.fixed_spend)}).",
                    f.fixed_spend - f.income / 2,
                    "bad",
                )
            )

    if len(f.subscriptions) >= 2:
        total = sum((a for _, a in f.subscriptions), ZERO)
        cards.append(
            Insight(
                "subscriptions",
                "Subscriptions add up",
                f"{inr(total)} a month across {len(f.subscriptions)} services: "
                + ", ".join(m for m, _ in f.subscriptions[:3])
                + ("…" if len(f.subscriptions) > 3 else "."),
                total,
                "neutral",
            )
        )

    habits = [m for m in f.merchants if m.count >= HABIT_MIN_COUNT]
    if habits:
        top = max(habits, key=lambda m: m.amount)
        cards.append(
            Insight(
                "habit",
                f"Your {top.merchant} habit",
                f"{inr(top.amount)} across {top.count} payments — "
                f"about {inr(top.amount / top.count)} each.",
                top.amount / 2,
                "neutral",
            )
        )

    if f.spending > 0 and f.spend_by_category:
        category_id, amount = max(f.spend_by_category.items(), key=lambda kv: kv[1])
        name = f.names.get(category_id, "Uncategorized")
        cards.append(
            Insight(
                "biggest",
                "Where most of it went",
                f"{name} took {inr(amount)} — {amount / f.spending * 100:.0f}% of your spending.",
                amount / 2,
                "neutral",
                category_id,
            )
        )

    cards.sort(key=lambda c: c.impact, reverse=True)
    # One card per category: a spike and "biggest" about the same category say the same thing.
    seen: set[uuid.UUID] = set()
    unique: list[Insight] = []
    for c in cards:
        if c.category_id is not None:
            if c.category_id in seen:
                continue
            seen.add(c.category_id)
        unique.append(c)
    return unique[:MAX_CARDS]
