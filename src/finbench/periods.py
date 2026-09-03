"""Period phrasing.

Spec section 6.2: name the period unambiguously. "FY2024" is exactly the
ambiguity being tested elsewhere in the benchmark, so it must never appear in
a prompt by accident - every period is spelled out with its calendar end date.
"""
from __future__ import annotations

import datetime as dt


def _pretty(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%B %-d, %Y")


def quarters_between(start: str | None, end: str) -> int:
    if start is None:
        return 0
    days = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
    return max(1, round(days / 91.31))


def phrase(start: str | None, end: str, qtrs: int | None = None) -> str:
    """Human-readable, unambiguous period description."""
    if qtrs is None:
        qtrs = quarters_between(start, end)
    if qtrs == 0:
        return f"as of {_pretty(end)}"
    if qtrs >= 4:
        return f"the fiscal year ended {_pretty(end)}"
    months = qtrs * 3
    word = {3: "three", 6: "six", 9: "nine"}.get(months, str(months))
    return f"the {word} months ended {_pretty(end)}"


def is_annual(start: str | None, end: str) -> bool:
    return quarters_between(start, end) >= 4


def phrase_for_form(form: str, end: str) -> str:
    """Period wording implied by the form type.

    A revenue question needs a duration, never an instant: "as of June 30" is
    balance-sheet wording and reads as a different question. 10-K periods are
    annual; 10-Q figures are quoted for the quarter.
    """
    if form.startswith("10-K"):
        return phrase(None, end, qtrs=4)
    return phrase(None, end, qtrs=1)
