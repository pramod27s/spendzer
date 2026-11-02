import uuid

from app.engine.categorizer import Categorizer, RuleSpec
from app.models.enums import Bucket, CategorizedBy, Direction, MatchType

FOOD, GROCERIES, SHOPPING, SUBS, SALARY = (uuid.uuid4() for _ in range(5))


def _rules(*extra: RuleSpec) -> Categorizer:
    base = [
        RuleSpec("swiggy", MatchType.CONTAINS, FOOD, Bucket.DISCRETIONARY),
        RuleSpec("instamart", MatchType.CONTAINS, GROCERIES, Bucket.VARIABLE),
        RuleSpec("amazon", MatchType.CONTAINS, SHOPPING, Bucket.DISCRETIONARY),
        RuleSpec("prime video", MatchType.CONTAINS, SUBS, Bucket.FIXED),
        RuleSpec("vi", MatchType.CONTAINS, SUBS, Bucket.FIXED),
        RuleSpec("salary", MatchType.CONTAINS, SALARY, Bucket.INCOME),
    ]
    return Categorizer([*base, *extra])


def test_global_keyword_match() -> None:
    match = _rules().categorize("Swiggy", "UPI/DR/1/SWIGGY", Direction.DEBIT)
    assert match is not None
    assert match.category_id == FOOD
    assert match.categorized_by == CategorizedBy.RULE


def test_longer_keyword_wins_at_equal_priority() -> None:
    match = _rules().categorize("Swiggy Instamart", "SWIGGY INSTAMART", Direction.DEBIT)
    assert match is not None and match.category_id == GROCERIES
    match = _rules().categorize("Amazon", "AMAZON PRIME VIDEO", Direction.DEBIT)
    assert match is not None and match.category_id == SUBS


def test_contains_is_whole_word() -> None:
    assert _rules().categorize("Car Service Centre", "CAR SERVICE", Direction.DEBIT) is None


def test_user_override_beats_global() -> None:
    cat = _rules(RuleSpec("Swiggy", MatchType.EXACT, GROCERIES, Bucket.VARIABLE, 0, is_user=True))
    match = cat.categorize("Swiggy", "UPI/DR/1/SWIGGY", Direction.DEBIT)
    assert match is not None
    assert match.category_id == GROCERIES
    assert match.categorized_by == CategorizedBy.OVERRIDE


def test_exact_matches_merchant_only() -> None:
    cat = Categorizer([RuleSpec("Raju Stores", MatchType.EXACT, GROCERIES, Bucket.VARIABLE)])
    assert cat.categorize("Raju Stores", "anything", Direction.DEBIT) is not None
    assert cat.categorize("Raju Stores Annex", "anything", Direction.DEBIT) is None


def test_regex_rule_and_invalid_regex_ignored() -> None:
    cat = Categorizer(
        [
            RuleSpec(r"zom(ato)?", MatchType.REGEX, FOOD, Bucket.DISCRETIONARY),
            RuleSpec(r"([", MatchType.REGEX, SHOPPING, Bucket.DISCRETIONARY),
        ]
    )
    match = cat.categorize("Zomato", "UPI ZOMATO", Direction.DEBIT)
    assert match is not None and match.category_id == FOOD


def test_direction_filters_buckets() -> None:
    # Income rules never categorize debits; spending rules never categorize credits.
    assert _rules().categorize("Acme", "SALARY ADVANCE REPAYMENT", Direction.DEBIT) is None
    assert _rules().categorize("Swiggy", "SWIGGY", Direction.CREDIT) is None
    match = _rules().categorize("Acme", "NEFT SALARY", Direction.CREDIT)
    assert match is not None and match.category_id == SALARY
