"""Turn one normalized transaction into stored fields: merchant, kind, category, layer."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.engine.categorizer import Categorizer
from app.engine.income import PastTxn, classify_credit
from app.engine.merchant import extract_merchant
from app.engine.sanitize import mask_card_numbers
from app.engine.transfers import OwnIdentity, classify_debit
from app.models.enums import Bucket, CategorizedBy, Direction, TxnKind

OTHER = "Other"
SELF_TRANSFER = "Self Transfer"
INVESTMENT = "Investment"
REFUND = "Refund"


@dataclass(frozen=True)
class CategoryRef:
    id: uuid.UUID
    name: str
    bucket: Bucket


class MlGuess(Protocol):
    @property
    def category_name(self) -> str: ...
    @property
    def confidence(self) -> float: ...
    @property
    def version(self) -> str: ...


class Predictor(Protocol):
    def predict(self, merchant: str, raw: str) -> MlGuess | None: ...


@dataclass
class EnrichContext:
    categorizer: Categorizer
    identity: OwnIdentity
    categories: list[CategoryRef]
    recent_debits: list[PastTxn] = field(default_factory=list)
    past_credits: list[PastTxn] = field(default_factory=list)
    ml: Predictor | None = None  # layer 3; skipped when no model has been trained
    ml_min_confidence: float = 0.6

    def __post_init__(self) -> None:
        self.by_id = {c.id: c for c in self.categories}
        self.by_name = {c.name: c for c in self.categories}

    def named(self, name: str) -> CategoryRef | None:
        return self.by_name.get(name)


@dataclass(frozen=True)
class Enriched:
    raw_description: str
    merchant: str
    kind: TxnKind
    category_id: uuid.UUID | None
    categorized_by: CategorizedBy
    ml_model_version: str | None = None


def kind_for_category(category: CategoryRef, direction: Direction) -> TxnKind:
    """The kind implied when a transaction lands in a category."""
    if category.bucket == Bucket.INCOME:
        return TxnKind.INCOME if direction == Direction.CREDIT else TxnKind.EXPENSE
    if category.bucket == Bucket.EXCLUDED:
        if category.name == INVESTMENT:
            return TxnKind.INVESTMENT
        if category.name == REFUND and direction == Direction.CREDIT:
            return TxnKind.REFUND
        return TxnKind.SELF_TRANSFER
    # A credit sitting in a spending category is money coming back for that spend.
    return TxnKind.EXPENSE if direction == Direction.DEBIT else TxnKind.REFUND


def enrich(
    ctx: EnrichContext,
    *,
    raw_description: str,
    txn_date: date,
    amount: Decimal,
    direction: Direction,
    merchant: str | None = None,
) -> Enriched:
    raw = mask_card_numbers(" ".join(raw_description.split()))
    merchant = (merchant or "").strip() or extract_merchant(raw)
    text = f"{merchant} {raw}"

    def _id(name: str) -> uuid.UUID | None:
        ref = ctx.named(name)
        return ref.id if ref else None

    override = ctx.categorizer.match_user(merchant, raw, direction)
    if override is not None:
        cat = ctx.by_id.get(override.category_id)
        kind = kind_for_category(cat, direction) if cat else TxnKind.EXPENSE
        return Enriched(raw, merchant, kind, override.category_id, CategorizedBy.OVERRIDE)

    if direction == Direction.CREDIT:
        result = classify_credit(
            text=text,
            merchant=merchant,
            amount=amount,
            txn_date=txn_date,
            identity=ctx.identity,
            recent_debits=ctx.recent_debits,
            past_credits=ctx.past_credits,
        )
        if result.kind == TxnKind.UNKNOWN:
            rule = ctx.categorizer.match_global(merchant, raw, direction)
            if rule is not None and (cat := ctx.by_id.get(rule.category_id)):
                return Enriched(
                    raw, merchant, kind_for_category(cat, direction), cat.id, CategorizedBy.RULE
                )
        return Enriched(raw, merchant, result.kind, _id(result.category_name), CategorizedBy.RULE)

    kind = classify_debit(text, ctx.identity)
    if kind == TxnKind.SELF_TRANSFER:
        return Enriched(raw, merchant, kind, _id(SELF_TRANSFER), CategorizedBy.RULE)
    if kind == TxnKind.INVESTMENT:
        return Enriched(raw, merchant, kind, _id(INVESTMENT), CategorizedBy.RULE)

    rule = ctx.categorizer.match_global(merchant, raw, direction)
    if rule is not None and (cat := ctx.by_id.get(rule.category_id)):
        return Enriched(
            raw, merchant, kind_for_category(cat, direction), cat.id, CategorizedBy.RULE
        )

    # Layer 3: the classifier, for merchants no rule knows — only when it's confident.
    if ctx.ml is not None:
        guess = ctx.ml.predict(merchant, raw)
        if guess is not None and guess.confidence >= ctx.ml_min_confidence:
            # "Other" is the model saying "this looks like paying a person": don't guess.
            cat = ctx.named(guess.category_name) if guess.category_name != OTHER else None
            if cat is not None and cat.bucket not in (Bucket.INCOME, Bucket.EXCLUDED):
                return Enriched(
                    raw, merchant, TxnKind.EXPENSE, cat.id, CategorizedBy.ML, guess.version
                )
    return Enriched(raw, merchant, TxnKind.EXPENSE, _id(OTHER), CategorizedBy.RULE)
