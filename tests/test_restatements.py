import json
import pathlib

from finbench import restatements

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "facts_mini.json"


def load():
    return json.loads(FIXTURE.read_text())


def test_finds_the_restated_period():
    found = restatements.find(load())
    assert len(found) == 1
    r = found[0]
    assert r.concept == "Revenues"
    assert r.superseded_value == 1000
    assert r.gold_value == 900


def test_records_both_accessions():
    r = restatements.find(load())[0]
    assert r.superseded_accn == "0001-23-000001"
    assert r.source_accn == "0001-24-000001"


def test_gold_is_the_most_recently_filed_not_the_largest():
    r = restatements.find(load())[0]
    assert r.gold_value < r.superseded_value


def test_immaterial_revisions_are_ignored():
    facts = load()
    facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"][1]["val"] = 1000.4
    assert restatements.find(facts) == []


def test_same_accession_duplicates_are_not_restatements():
    facts = load()
    rows = facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    rows[1]["accn"] = rows[0]["accn"]
    rows[1]["filed"] = rows[0]["filed"]
    assert restatements.find(facts) == []


def test_unscored_forms_are_excluded():
    facts = load()
    facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"][1]["form"] = "8-K"
    assert restatements.find(facts) == []


def _facts(pairs, concept="Revenues"):
    """Build a minimal companyfacts doc with two filings of one period."""
    rows = [
        {"start": "2023-01-01", "end": "2023-12-31", "val": pairs[0],
         "accn": "0001-23-000001", "fy": 2023, "fp": "FY", "form": "10-K",
         "filed": "2024-02-01"},
        {"start": "2023-01-01", "end": "2023-12-31", "val": pairs[1],
         "accn": "0001-24-000001", "fy": 2024, "fp": "FY", "form": "10-K",
         "filed": "2025-02-01"},
    ]
    return {"facts": {"us-gaap": {concept: {"units": {"USD": rows}}}}}


def test_newly_tagged_concept_is_not_a_restatement():
    # GE: `was 0 -> now 213,514,000,000`. The concept was absent-as-zero in the
    # earlier filing, not restated. Relative change is meaningless here.
    assert restatements.find(_facts([0, 213_514_000_000])) == []
    assert restatements.find(_facts([5_000_000, 0])) == []


def test_units_change_is_not_a_restatement():
    # 3M: `34,965 -> 34,965,000` is a thousands->units retag, not a revision.
    assert restatements.find(_facts([34_965, 34_965_000])) == []
    assert restatements.find(_facts([1_200_000, 1_200])) == []


def test_a_real_revision_near_a_scale_boundary_still_counts():
    # Guard the scale filter against swallowing genuine large revisions.
    found = restatements.find(_facts([1_000_000, 1_400_000]))
    assert len(found) == 1


def test_concept_allowlist_filters_to_analyst_meaningful_tags():
    facts = _facts([1000, 900], concept="IncomeTaxHolidayIncomeTaxBenefitsPerShare")
    assert restatements.find(facts) == []
    assert len(restatements.find(facts, concepts=None)) == 1
    assert len(restatements.find(_facts([1000, 900], concept="Revenues"))) == 1
