"""Strip full card numbers from narrations before anything is stored."""

import re

# 13-19 digits, optionally grouped by spaces/dashes. 12-digit runs are left alone: they are
# almost always UPI RRNs, which phase 4 dedup needs (see docs/DECISIONS.md).
_CARD_RUN = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def mask_card_numbers(text: str) -> str:
    def _mask(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return "X" * (len(digits) - 4) + digits[-4:]
        return match.group(0)

    return _CARD_RUN.sub(_mask, text)


def normalize_last4(value: str | None) -> str | None:
    """Keep only the last 4 digits of whatever account/card number the user typed."""
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits[-4:] if len(digits) >= 4 else None
