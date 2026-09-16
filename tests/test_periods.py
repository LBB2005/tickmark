from finbench import periods


def test_annual_period_named_with_calendar_end():
    assert periods.phrase("2024-01-01", "2024-12-31") == "the fiscal year ended December 31, 2024"


def test_non_calendar_fiscal_year_is_still_explicit():
    # Costco's August year-end is exactly the trap the benchmark tests, so the
    # prompt must never say "fiscal 2024" alone.
    assert periods.phrase("2023-09-04", "2024-09-01") == "the fiscal year ended September 1, 2024"


def test_quarter_and_half_year():
    assert periods.phrase("2025-04-01", "2025-06-30") == "the three months ended June 30, 2025"
    assert periods.phrase("2025-01-01", "2025-06-30") == "the six months ended June 30, 2025"


def test_instant_period():
    assert periods.phrase(None, "2025-06-30") == "as of June 30, 2025"


def test_quarters_between_rounds_to_nearest_quarter():
    assert periods.quarters_between("2025-04-01", "2025-06-30") == 1
    assert periods.quarters_between("2024-01-01", "2024-12-31") == 4
    assert periods.quarters_between(None, "2024-12-31") == 0


def test_is_annual():
    assert periods.is_annual("2024-01-01", "2024-12-31")
    assert not periods.is_annual("2025-04-01", "2025-06-30")


def test_phrase_for_form_gives_durations_not_instants():
    # A revenue question must never be phrased "as of <date>".
    assert periods.phrase_for_form("10-K", "2026-06-30") == "the fiscal year ended June 30, 2026"
    assert periods.phrase_for_form("10-Q", "2026-06-30") == "the three months ended June 30, 2026"
    assert "as of" not in periods.phrase_for_form("10-Q", "2026-06-30")


def test_week_based_periods_are_named_in_weeks():
    # Costco reports 12-, 16- and 24-week periods. "Three months ended" is a
    # different span than the one the filing reports.
    assert periods.phrase("2026-02-16", "2026-05-10") == "the 12 weeks ended May 10, 2026"
    assert periods.phrase("2023-09-04", "2024-02-18") == "the 24 weeks ended February 18, 2024"


def test_13_and_39_week_periods_still_read_as_months():
    # A 52/53-week filer's 13-week quarter is what everyone calls a quarter.
    assert periods.phrase("2024-01-01", "2024-03-31") == "the three months ended March 31, 2024"
    assert periods.phrase("2023-06-01", "2024-02-29") == "the nine months ended February 29, 2024"


def test_fiscal_year_end_match_allows_52_53_week_drift():
    assert periods.ends_at_fiscal_year_end("2024-12-31", "1231")
    assert periods.ends_at_fiscal_year_end("2024-12-28", "1231")
    # Year-wrap: J&J's fiscalYearEnd is "0103" but its years end around Dec 29.
    assert periods.ends_at_fiscal_year_end("2024-12-29", "0103")
    assert periods.ends_at_fiscal_year_end("2026-01-31", "0131")


def test_trailing_twelve_months_is_not_a_fiscal_year():
    # Amazon files TTM free-cash-flow inputs ending September 30. Twelve months
    # long, but not Amazon's fiscal year, so it must never be labeled one.
    assert not periods.ends_at_fiscal_year_end("2016-09-30", "1231")


def test_unknown_fiscal_year_end_does_not_reject():
    assert periods.ends_at_fiscal_year_end("2016-09-30", None)


def test_one_extra_week_is_still_a_quarter_or_nine_months():
    # Broadcom's 14-week Q1 FY2024 and Western Digital's 40-week nine months.
    assert periods.phrase("2023-10-30", "2024-02-04") == "the three months ended February 4, 2024"
    assert periods.phrase("2025-06-28", "2026-04-03") == "the nine months ended April 3, 2026"
