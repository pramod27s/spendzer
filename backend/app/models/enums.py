from enum import StrEnum

from sqlalchemy import Enum


class AccountType(StrEnum):
    BANK = "bank"
    UPI = "upi"
    CARD = "card"
    CASH = "cash"


class UploadStatus(StrEnum):
    PENDING = "pending"
    NEEDS_MAPPING = "needs_mapping"
    PARSING = "parsing"
    DONE = "done"
    FAILED = "failed"


class Direction(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class TxnKind(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    REFUND = "refund"
    CASHBACK = "cashback"
    SELF_TRANSFER = "self_transfer"
    INVESTMENT = "investment"
    UNKNOWN = "unknown"


class CategorizedBy(StrEnum):
    RULE = "rule"
    OVERRIDE = "override"
    ML = "ml"
    USER = "user"


class Bucket(StrEnum):
    FIXED = "fixed"
    VARIABLE = "variable"
    DISCRETIONARY = "discretionary"
    INCOME = "income"
    EXCLUDED = "excluded"


class MatchType(StrEnum):
    CONTAINS = "contains"
    REGEX = "regex"
    EXACT = "exact"


class Frequency(StrEnum):
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    YEARLY = "yearly"


class RecurringStatus(StrEnum):
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"  # never re-created by detection


class PlanStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class PlanItemSource(StrEnum):
    FIXED = "fixed"
    FORECAST = "forecast"
    USER = "user"


def str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """VARCHAR + CHECK constraint; easier to evolve than native PG enums."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
