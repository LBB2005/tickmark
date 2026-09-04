import json
import pathlib

from finbench import screen_density

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "facts_mini.json"


def test_scores_a_single_company():
    facts = json.loads(FIXTURE.read_text())
    row = screen_density.score(
        ticker="TEST", cik=1, name="Testco", role="A", facts=facts,
        segment_members=7, segment_facts=30)
    assert row["n_restatements"] == 1
    assert row["n_concepts"] == 1
    assert row["n_segment_members"] == 7
    assert row["n_segment_facts"] == 30
    assert row["public_float"] == 5000000000


def test_verdict_flags_thin_recast_parent():
    row = screen_density.score(
        ticker="T", cik=1, name="T", role="A", facts={"facts": {}},
        segment_members=0, segment_facts=0)
    assert row["verdict"] == "THIN"


def test_verdict_is_role_aware():
    # Role A is judged on restatements and ignores segment richness.
    assert screen_density.verdict("A", n_restatements=5, n_segment_facts=0) == "KEEP"
    assert screen_density.verdict("A", n_restatements=1, n_segment_facts=99) == "THIN"
    # Role C is judged the other way round.
    assert screen_density.verdict("C", n_restatements=0, n_segment_facts=9) == "KEEP"
    assert screen_density.verdict("C", n_restatements=99, n_segment_facts=1) == "THIN"


def test_thresholds_follow_the_spec_supply_table():
    # C must supply 4 buried questions, F 2. G is not segment-judged at all.
    assert screen_density.verdict("C", n_restatements=0, n_segment_facts=4) == "KEEP"
    assert screen_density.verdict("C", n_restatements=0, n_segment_facts=3) == "THIN"
    assert screen_density.verdict("F", n_restatements=0, n_segment_facts=2) == "KEEP"
    assert screen_density.verdict("F", n_restatements=0, n_segment_facts=1) == "THIN"


def test_covenant_role_never_pends_on_missing_segment_data():
    # G resolves from restatements alone, so it is decided even with no cache.
    assert screen_density.verdict("G", n_restatements=40, n_segment_facts=None) == "KEEP"


def test_segment_roles_are_pending_before_dimensional_data_exists():
    # Not THIN: 21 companies would otherwise look rejected by a screen that
    # simply has not run yet.
    assert screen_density.verdict("C", n_restatements=99, n_segment_facts=None) == "PENDING"
    assert screen_density.verdict("F", n_restatements=0, n_segment_facts=None) == "PENDING"
    # Roles judged on restatements are unaffected by missing segment data.
    assert screen_density.verdict("A", n_restatements=9, n_segment_facts=None) == "KEEP"


def test_covenant_role_is_judged_on_restatements_not_segments():
    # Role G supplies covenant questions from prose; segment richness is
    # irrelevant to it and must not be able to drop the company.
    assert screen_density.verdict("G", n_restatements=40, n_segment_facts=0) == "KEEP"
    assert screen_density.verdict("G", n_restatements=0, n_segment_facts=99) == "THIN"


def test_short_history_spinoffs_are_never_thin():
    # Role B is wanted precisely because it is thin.
    assert screen_density.verdict("B", n_restatements=0, n_segment_facts=0) == "KEEP"
