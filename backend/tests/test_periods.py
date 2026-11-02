from datetime import date

import pytest

from app.core.errors import AppError
from app.services.analytics_service import resolve_period

TODAY = date(2026, 11, 15)


def test_this_month_and_previous() -> None:
    period, prev = resolve_period("this_month", None, None, TODAY)
    assert (period.start, period.end) == (date(2026, 11, 1), date(2026, 11, 30))
    assert (prev.start, prev.end) == (date(2026, 10, 1), date(2026, 10, 31))
    assert period.label == "November 2026"


def test_last_month_crosses_year() -> None:
    period, prev = resolve_period("last_month", None, None, date(2026, 1, 10))
    assert (period.start, period.end) == (date(2025, 12, 1), date(2025, 12, 31))
    assert (prev.start, prev.end) == (date(2025, 11, 1), date(2025, 11, 30))


def test_last_3_includes_current_month() -> None:
    period, prev = resolve_period("last_3", None, None, TODAY)
    assert (period.start, period.end) == (date(2026, 9, 1), date(2026, 11, 30))
    assert (prev.start, prev.end) == (date(2026, 6, 1), date(2026, 8, 31))


def test_custom_whole_month_and_arbitrary_range() -> None:
    period, prev = resolve_period("custom", date(2026, 10, 1), date(2026, 10, 31), TODAY)
    assert (prev.start, prev.end) == (date(2026, 9, 1), date(2026, 9, 30))
    period, prev = resolve_period("custom", date(2026, 10, 10), date(2026, 10, 19), TODAY)
    assert (prev.start, prev.end) == (date(2026, 9, 30), date(2026, 10, 9))


def test_custom_requires_valid_range() -> None:
    with pytest.raises(AppError):
        resolve_period("custom", None, None, TODAY)
    with pytest.raises(AppError):
        resolve_period("custom", date(2026, 10, 10), date(2026, 10, 1), TODAY)
