"""Indian-style rupee formatting for messages, tooltips and insight text."""

from decimal import ROUND_HALF_UP, Decimal


def inr(value: Decimal) -> str:
    """₹1,23,456 — whole rupees, Indian digit grouping."""
    n = int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts: list[str] = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return f"{'-' if n < 0 else ''}₹{s}"
