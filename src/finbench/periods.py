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
    weeks = _whole_weeks_off_calendar(start, end, qtrs)
    if weeks:
        return f"the {weeks} weeks ended {_pretty(end)}"
    months = qtrs * 3
    word = {3: "three", 6: "six", 9: "nine"}.get(months, str(months))
    return f"the {word} months ended {_pretty(end)}"


# How far a whole-week span may sit from the calendar quarter length before it
# stops reading as "N months". One extra week is 52/53-week drift: Broadcom's
# 14-week quarter and Western Digital's 40-week nine months are still what
# those companies call a quarter and nine months. Costco's 12-week quarter
# (84 days against 91) and 24-week half are not.
WEEK_DRIFT_DAYS = 7


def _whole_weeks_off_calendar(start: str | None, end: str, qtrs: int) -> int | None:
    """Week count for a period a filer reports in weeks, else None."""
    if start is None:
        return None
    # companyfacts dates are inclusive: a 12-week period starts on day 1 and
    # ends on day 84.
    days = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days + 1
    if days % 7 or abs(days - qtrs * 91.31) <= WEEK_DRIFT_DAYS:
        return None
    return days // 7


def ends_at_fiscal_year_end(end: str, fiscal_year_end: str | None,
                            tolerance_days: int = 7) -> bool:
    """Whether a period end date is this company's fiscal year-end.

    `fiscal_year_end` is the MMDD string from EDGAR submissions. 52/53-week
    filers drift up to a week either side of it, across the year boundary
    (J&J reports "0103" and closes years on December 29). A twelve-month span
    ending anywhere else - Amazon's trailing twelve months to September - is
    not a fiscal year and must not be called one. Unknown year-ends pass.
    """
    if not fiscal_year_end:
        return True
    month, day = int(fiscal_year_end[:2]), int(fiscal_year_end[2:])
    target = dt.date.fromisoformat(end)
    for year in (target.year - 1, target.year, target.year + 1):
        try:
            anchor = dt.date(year, month, day)
        except ValueError:  # 0229 in a non-leap year
            anchor = dt.date(year, month, 28)
        if abs((target - anchor).days) <= tolerance_days:
            return True
    return False


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
