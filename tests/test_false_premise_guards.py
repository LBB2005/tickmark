"""Guards that keep a false premise actually false (spec 6.1, 6.5)."""
import build_gold as bg


def test_generic_xbrl_buckets_are_rejected():
    # "What was Salesforce's All Other Segments revenue" is a trick phrasing,
    # not the plausible-but-absent segment the spec asks for.
    for label in ("All Other Segments", "Corporate", "Unallocated",
                  "Intersegment Eliminations", "Consolidated"):
        assert bg.is_generic_member(label), label


def test_real_segment_names_survive():
    for label in ("Innovative Medicine", "Aviation Segment", "Med Tech",
                  "Connected Fitness", "Data Center Solutions"):
        assert not bg.is_generic_member(label), label


def test_region_matching_the_targets_footprint_is_rejected():
    # WK Kellogg is the North American spin-off. Its members are spelled
    # UNITED STATES and CANADA, so a literal check never sees "North America".
    geo = {"united states", "canada", "other countries"}
    assert bg.collides_with_footprint("North America Segment", geo, "WK Kellogg Co")


def test_regions_the_target_does_not_operate_in_survive():
    geo = {"united states", "canada", "other countries"}
    assert not bg.collides_with_footprint("Latin America Segment", geo, "WK Kellogg Co")
    assert not bg.collides_with_footprint("AMEA", geo, "WK Kellogg Co")


def test_europe_alias_is_caught_for_a_european_reporter():
    geo = {"germany", "united kingdom"}
    assert bg.collides_with_footprint("Europe Segment", geo, "Some AG")


def test_non_geographic_segment_names_are_unaffected_by_footprint_guard():
    geo = {"united states", "canada"}
    assert not bg.collides_with_footprint("Innovative Medicine", geo, "WK Kellogg Co")


def test_a_member_that_is_only_boilerplate_is_unnameable():
    # Carvana and Elanco tag a bare "ReportableSegmentMember", which leaves
    # nothing to name: the question renders as "in the  segment".
    for label in ("Reportable Segment", "Segment", "Operating Segment",
                  "Member"):
        assert bg.is_unnameable_member(label), label


def test_a_real_segment_name_is_nameable():
    for label in ("Aviation Segment", "Med Tech", "Converse"):
        assert not bg.is_unnameable_member(label), label
