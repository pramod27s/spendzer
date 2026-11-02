"""Layered categorization: user override -> global rules -> (ML, phase 4) -> uncategorized."""

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from app.models.enums import Bucket, CategorizedBy, Direction, MatchType

_CREDIT_BUCKETS = frozenset({Bucket.INCOME, Bucket.EXCLUDED})


@dataclass(frozen=True)
class RuleSpec:
    pattern: str
    match_type: MatchType
    category_id: uuid.UUID
    bucket: Bucket
    priority: int = 100
    is_user: bool = False


@dataclass(frozen=True)
class CategoryMatch:
    category_id: uuid.UUID
    categorized_by: CategorizedBy
    bucket: Bucket


@dataclass(frozen=True)
class _CompiledRule:
    spec: RuleSpec
    regex: re.Pattern[str] | None


def _compile(spec: RuleSpec) -> _CompiledRule | None:
    if spec.match_type == MatchType.EXACT:
        return _CompiledRule(spec, None)
    try:
        if spec.match_type == MatchType.REGEX:
            return _CompiledRule(spec, re.compile(spec.pattern, re.IGNORECASE))
        # contains: whole-word match so "vi" doesn't hit "service"
        return _CompiledRule(spec, re.compile(rf"\b{re.escape(spec.pattern.lower())}\b"))
    except re.error:
        return None


def _sort_key(rule: _CompiledRule) -> tuple[int, int]:
    # Lower priority number wins; among equals, the longer (more specific) pattern wins,
    # so "instamart" (Groceries) beats "swiggy" (Food & Dining).
    return (rule.spec.priority, -len(rule.spec.pattern))


class Categorizer:
    def __init__(self, rules: Iterable[RuleSpec]) -> None:
        compiled = [c for c in (_compile(r) for r in rules) if c is not None]
        self._user = sorted((c for c in compiled if c.spec.is_user), key=_sort_key)
        self._global = sorted((c for c in compiled if not c.spec.is_user), key=_sort_key)

    @staticmethod
    def _applies(rule: _CompiledRule, direction: Direction) -> bool:
        is_credit_bucket = rule.spec.bucket in _CREDIT_BUCKETS
        if direction == Direction.CREDIT:
            return is_credit_bucket
        return rule.spec.bucket != Bucket.INCOME

    @staticmethod
    def _hit(rule: _CompiledRule, merchant: str, text: str) -> bool:
        if rule.regex is None:
            return merchant.strip().lower() == rule.spec.pattern.strip().lower()
        return rule.regex.search(text) is not None

    def _first(
        self, rules: list[_CompiledRule], merchant: str, text: str, direction: Direction
    ) -> RuleSpec | None:
        for rule in rules:
            if self._applies(rule, direction) and self._hit(rule, merchant, text):
                return rule.spec
        return None

    def match_user(self, merchant: str, raw: str, direction: Direction) -> CategoryMatch | None:
        spec = self._first(self._user, merchant, f"{merchant} {raw}".lower(), direction)
        if spec is None:
            return None
        return CategoryMatch(spec.category_id, CategorizedBy.OVERRIDE, spec.bucket)

    def match_global(self, merchant: str, raw: str, direction: Direction) -> CategoryMatch | None:
        spec = self._first(self._global, merchant, f"{merchant} {raw}".lower(), direction)
        if spec is None:
            return None
        return CategoryMatch(spec.category_id, CategorizedBy.RULE, spec.bucket)

    def categorize(self, merchant: str, raw: str, direction: Direction) -> CategoryMatch | None:
        return self.match_user(merchant, raw, direction) or self.match_global(
            merchant, raw, direction
        )
