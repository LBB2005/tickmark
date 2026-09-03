import json
import pathlib

from finbench import screen_density

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "facts_mini.json"


def test_scores_a_single_company():
    facts = json.loads(FIXTURE.read_text())
    row = screen_density.score(
        ticker="TEST", cik=1, name="Testco", role="A", facts=facts, segment_members=7)
    assert row["n_restatements"] == 1
    assert row["n_concepts"] == 1
    assert row["n_segment_members"] == 7
    assert row["public_float"] == 5000000000


def test_verdict_flags_thin_recast_parent():
    row = screen_density.score(
        ticker="T", cik=1, name="T", role="A", facts={"facts": {}}, segment_members=0)
    assert row["verdict"] == "THIN"


def test_verdict_is_role_aware():
    # Role A is judged on restatements and ignores segment richness.
    assert screen_density.verdict("A", n_restatements=5, n_segment_members=0) == "KEEP"
    assert screen_density.verdict("A", n_restatements=1, n_segment_members=99) == "THIN"
    # Role C is judged the other way round.
    assert screen_density.verdict("C", n_restatements=0, n_segment_members=9) == "KEEP"
    assert screen_density.verdict("C", n_restatements=99, n_segment_members=1) == "THIN"


def test_segment_roles_are_pending_before_dimensional_data_exists():
    # Not THIN: 21 companies would otherwise look rejected by a screen that
    # simply has not run yet.
    assert screen_density.verdict("C", n_restatements=99, n_segment_members=None) == "PENDING"
    assert screen_density.verdict("F", n_restatements=0, n_segment_members=None) == "PENDING"
    # Roles judged on restatements are unaffected by missing segment data.
    assert screen_density.verdict("A", n_restatements=9, n_segment_members=None) == "KEEP"


def test_short_history_spinoffs_are_never_thin():
    # Role B is wanted precisely because it is thin.
    assert screen_density.verdict("B", n_restatements=0, n_segment_members=0) == "KEEP"
