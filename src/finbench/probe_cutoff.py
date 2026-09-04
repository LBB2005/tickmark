"""Cutoff-elicitation probe (spec section 7.4).

"Post-cutoff" is not a global property of a question. A period that postdates
one model's training is in-distribution for another, so scoring every model
against one fixed set of post-cutoff questions is invalid.

Two things are needed and this handles both: ask each model what it believes
its own cutoff is, and record it so the post-cutoff bucket can be scored
against each model's own boundary. Stated cutoffs are often vague or wrong,
which is itself reportable - a model that misjudges its own boundary cannot
know when to abstain.
"""
from __future__ import annotations

import datetime as dt
import re

PROMPT = (
    "What is your knowledge cutoff date? Answer with the month and year only, "
    "in the exact format YYYY-MM, and nothing else. If you are uncertain, give "
    "your best single estimate rather than a range."
)

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def parse_cutoff(text: str | None) -> str | None:
    """Pull a YYYY-MM out of a free-text answer.

    Models ignore the format instruction often enough that a bare regex on
    YYYY-MM alone loses real answers ("my knowledge cutoff is April 2024").
    """
    if not text:
        return None
    cleaned = text.strip()
    match = re.search(r"\b(19|20)\d{2}[-/](0?[1-9]|1[0-2])\b", cleaned)
    if match:
        year, month = re.split(r"[-/]", match.group(0))
        return f"{year}-{int(month):02d}"
    match = re.search(r"\b([A-Za-z]+)\s+((?:19|20)\d{2})\b", cleaned)
    if match and match.group(1).lower() in MONTHS:
        return f"{match.group(2)}-{MONTHS[match.group(1).lower()]:02d}"
    match = re.search(r"\b((?:19|20)\d{2})\b", cleaned)
    if match:
        return f"{match.group(1)}-12"   # year only: assume end of year
    return None


def is_post_cutoff(period_end: str, stated_cutoff: str | None) -> bool | None:
    """Whether a period ends after a model's stated cutoff. None if unknown."""
    if not stated_cutoff:
        return None
    end = dt.date.fromisoformat(period_end)
    year, month = (int(x) for x in stated_cutoff.split("-"))
    # A cutoff of YYYY-MM includes that whole month.
    last_day = dt.date(year + month // 12, month % 12 + 1, 1) - dt.timedelta(days=1)
    return end > last_day
