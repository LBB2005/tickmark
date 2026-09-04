from finbench import probe_cutoff as p


def test_parses_the_requested_format():
    assert p.parse_cutoff("2024-04") == "2024-04"
    assert p.parse_cutoff("2024-4") == "2024-04"


def test_parses_prose_answers_models_actually_give():
    assert p.parse_cutoff("My knowledge cutoff is April 2024.") == "2024-04"
    assert p.parse_cutoff("I was trained on data up to August 2025") == "2025-08"


def test_year_only_assumes_december():
    assert p.parse_cutoff("sometime in 2024") == "2024-12"


def test_unparseable_returns_none():
    assert p.parse_cutoff("I don't know") is None
    assert p.parse_cutoff("") is None
    assert p.parse_cutoff(None) is None


def test_post_cutoff_boundary_includes_the_stated_month():
    # A cutoff of 2026-03 covers all of March.
    assert p.is_post_cutoff("2026-03-31", "2026-03") is False
    assert p.is_post_cutoff("2026-04-01", "2026-03") is True


def test_year_end_rollover():
    assert p.is_post_cutoff("2025-12-31", "2025-12") is False
    assert p.is_post_cutoff("2026-01-01", "2025-12") is True


def test_unknown_cutoff_is_none_not_false():
    # Silently treating an unknown cutoff as "not post-cutoff" would score the
    # whole bucket wrong for that model.
    assert p.is_post_cutoff("2026-06-30", None) is None
