from finbench import false_premise as fp
from finbench.dimensional import SegmentFact


def _fact(cik, member, label):
    return SegmentFact(cik=cik, concept="Revenues", axis="BusinessSegments",
                       member=member, member_label=label, unit="USD",
                       start=None, end="2025-12-31", qtrs=4, val=1.0,
                       accn="a", form="10-K", filed="2026-02-01")


def test_short_geographic_member_does_not_match_long_segment_name():
    # "US" inside "SafetyAndIndustrial" was a real false alarm.
    assert not fp.matches("Safety And Industrial Segment", "US")
    assert not fp.matches("Latin America Segment", "CA")


def test_exact_match_after_normalisation():
    assert fp.matches("Med Tech Segment", "MedTechMember")
    assert fp.matches("Innovative Medicine", "Innovative Medicine Segment")


def test_long_substring_still_collides():
    assert fp.matches("Purification And Filtration Segment", "PurificationAndFiltration")


def test_check_confirms_absence():
    facts = [_fact(1, "MedTechMember", "Med Tech Segment")]
    out = fp.check([{"question_id": "q1", "category": "false_premise", "cik": 1,
                     "nonexistent_segment": "Aviation Segment"}], facts)
    assert out[0].status == "absent_confirmed"


def test_check_flags_a_true_premise_as_collision():
    facts = [_fact(1, "MedTechMember", "Med Tech Segment")]
    out = fp.check([{"question_id": "q1", "category": "false_premise", "cik": 1,
                     "nonexistent_segment": "Med Tech Segment"}], facts)
    assert out[0].status == "collision"


def test_company_with_no_segment_data_is_not_claimed_confirmed():
    out = fp.check([{"question_id": "q1", "category": "false_premise", "cik": 99,
                     "nonexistent_segment": "Anything"}], [])
    assert out[0].status == "no_segment_data"


def test_non_false_premise_records_are_ignored():
    assert fp.check([{"question_id": "q", "category": "buried", "cik": 1}], []) == []
