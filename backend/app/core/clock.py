"""One place to ask for today's date, so tests can pin it."""

from datetime import date


def today() -> date:
    return date.today()
