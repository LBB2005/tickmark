import datetime as dt

from finbench import dimensional
from finbench.dimensional import SegmentFact


def test_parse_segments_splits_multi_axis():
    assert dimensional.parse_segments(
        "BusinessSegments=PECOEnergyCo;ConsolidationItems=OperatingSegments;"
    ) == {"BusinessSegments": "PECOEnergyCo",
          "ConsolidationItems": "OperatingSegments"}


def test_parse_segments_handles_empty():
    assert dimensional.parse_segments("") == {}


def test_humanise_prefers_sec_label_and_strips_member_bracket():
    assert dimensional.humanise_member("Aviation Segment [Member]", "AviationSegmentMember") \
        == "Aviation Segment"


def test_humanise_falls_back_to_splitting_camel_case():
    assert dimensional.humanise_member(None, "InnovativeMedicine") == "Innovative Medicine"
    assert dimensional.humanise_member("", "MedTechMember") == "Med Tech"


def test_start_for_duration_and_instant():
    assert dimensional._start_for("2025-06-30", 0) is None
    assert dimensional._start_for("2025-06-30", 1) == "2025-03-30"
    assert dimensional._start_for("2025-06-30", 4) == "2024-06-30"


def test_period_label_reads_like_a_question():
    def fact(qtrs, end="2025-06-30"):
        return SegmentFact(
            cik=1, concept="Revenues", axis="BusinessSegments", member="M",
            member_label="Med Tech", unit="USD",
            start=dimensional._start_for(end, qtrs), end=end, qtrs=qtrs,
            val=1.0, accn="a", form="10-Q", filed="2025-08-01")

    assert fact(0).period_label == "as of June 30, 2025"
    assert fact(1).period_label == "the three months ended June 30, 2025"
    assert fact(2).period_label == "the six months ended June 30, 2025"
    assert fact(4).period_label == "the fiscal year ended June 30, 2025"


def test_recent_months_starts_one_month_back_and_wraps_year():
    assert dimensional.recent_months(3, dt.date(2026, 2, 15)) == ["2026_01", "2025_12", "2025_11"]
    assert dimensional.recent_months(2, dt.date(2026, 9, 2)) == ["2026_08", "2026_07"]


def test_operating_segments_qualifier_is_not_ambiguity():
    # ConsolidationItems=OperatingSegments means "this row IS the segment".
    parsed = {"BusinessSegments": "MedTech", "ConsolidationItems": "OperatingSegments"}
    assert dimensional.usable_member(parsed, "BusinessSegments") == "MedTech"


def test_reconciliation_rows_are_rejected():
    for bad in ("IntersegmentElimination", "CorporateNonSegment", "MaterialReconcilingItems"):
        parsed = {"BusinessSegments": "MedTech", "ConsolidationItems": bad}
        assert dimensional.usable_member(parsed, "BusinessSegments") is None


def test_product_split_within_a_segment_is_rejected():
    parsed = {"BusinessSegments": "MedTech", "ConsolidationItems": "OperatingSegments",
              "ProductOrService": "Surgery"}
    assert dimensional.usable_member(parsed, "BusinessSegments") is None


def test_geographic_split_within_a_segment_is_rejected():
    parsed = {"BusinessSegments": "MedTech", "Geographical": "US"}
    assert dimensional.usable_member(parsed, "BusinessSegments") is None
    # ...and the same fact is not usable as a pure geographic fact either.
    assert dimensional.usable_member(parsed, "Geographical") is None


def test_pure_axis_with_no_companions_is_usable():
    assert dimensional.usable_member({"BusinessSegments": "Aviation"}, "BusinessSegments") == "Aviation"
    assert dimensional.usable_member({"Geographical": "Americas"}, "Geographical") == "Americas"


def test_missing_axis_returns_none():
    assert dimensional.usable_member({"Geographical": "US"}, "BusinessSegments") is None
