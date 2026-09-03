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
