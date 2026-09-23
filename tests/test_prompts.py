"""The rendered question is the measurement instrument.

Two properties matter more than wording. A false-premise question must be
indistinguishable from a real segment question, and a post-cutoff question
from an answerable one - otherwise the model detects the category instead of
recalling the figure. Both are asserted directly.
"""
from __future__ import annotations

import json

import pytest

from finbench import prompts


def record(**overrides):
    base = {
        "question_id": "bur-m-BAX-x",
        "company": "BAXTER INTERNATIONAL INC",
        "cik": 10456,
        "fiscal_period": "the three months ended June 30, 2026",
        "fiscal_period_end": "2026-06-30",
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "answer_type": "numeric",
        "gold_value": 2076000000.0,
        "gold_unit": "USD",
        "superseded_value": None,
        "category": "buried",
        "difficulty": "mid",
        "segment_label": "Medical Products And Therapies",
        "segment_axis": "BusinessSegments",
    }
    base.update(overrides)
    return base


def test_question_names_company_ticker_concept_and_period():
    text = prompts.question_text(record(), ticker="BAX")
    assert "BAXTER INTERNATIONAL INC (BAX)" in text
    assert "revenue" in text.lower()
    assert "the three months ended June 30, 2026" in text
    assert text.endswith("?")


def test_business_segment_question_says_segment():
    text = prompts.question_text(record(), ticker="BAX")
    assert "Medical Products And Therapies segment" in text


def test_geographic_question_does_not_say_segment():
    text = prompts.question_text(
        record(segment_label="UNITED STATES", segment_axis="Geographical"),
        ticker="BAX",
    )
    assert "UNITED STATES" in text
    assert "segment" not in text


def test_false_premise_question_is_identical_in_form_to_a_real_one():
    real = prompts.question_text(record(), ticker="BAX")
    fake = prompts.question_text(
        record(
            category="false_premise",
            answer_type="none_exists",
            gold_value=None,
            difficulty=None,
            segment_label=None,
            segment_axis=None,
            nonexistent_segment="Medical Products And Therapies",
        ),
        ticker="BAX",
    )
    assert fake == real


def test_post_cutoff_question_is_identical_in_form_to_an_answerable_one():
    answerable = prompts.question_text(
        record(category="buried", difficulty=None, segment_label=None,
               segment_axis=None, concept="Revenues"),
        ticker="BAX",
    )
    post = prompts.question_text(
        record(category="post_cutoff", answer_type="post_cutoff",
               gold_value=None, difficulty=None, segment_label=None,
               segment_axis=None, concept="Revenues"),
        ticker="BAX",
    )
    assert post == answerable


def test_share_count_question_reads_as_a_count_not_an_amount():
    text = prompts.question_text(
        record(concept="EntityCommonStockSharesOutstanding",
               fiscal_period="as of July 31, 2026", gold_unit="shares",
               segment_label=None, segment_axis=None),
        ticker="BAX",
    )
    assert "shares of common stock" in text
    assert "as of July 31, 2026" in text


def test_unknown_concept_is_a_hard_error_not_a_raw_xbrl_tag():
    with pytest.raises(KeyError):
        prompts.question_text(record(concept="MadeUpConceptTag"), ticker="BAX")


def test_messages_carry_the_question_and_the_response_schema():
    messages = prompts.build_messages(record(), ticker="BAX")
    assert [m["role"] for m in messages] == ["system", "user"]
    user = messages[1]["content"]
    assert prompts.question_text(record(), ticker="BAX") in user
    for field in ("answer", "unit", "confidence", "abstain", "note"):
        assert field in user


def test_system_message_forbids_tools_and_asks_for_json_only():
    system = prompts.build_messages(record(), ticker="BAX")[0]["content"]
    lowered = system.lower()
    assert "json" in lowered
    assert "memory" in lowered or "closed-book" in lowered


def test_prompt_never_reveals_the_answer_or_the_category():
    rec = record()
    user = prompts.build_messages(rec, ticker="BAX")[1]["content"]
    assert "2076000000" not in user.replace(",", "")
    assert "buried" not in user
    assert "false_premise" not in user


def test_schema_example_parses_as_json():
    json.loads(prompts.RESPONSE_SCHEMA_EXAMPLE)


def test_ticker_lookup_uses_the_pinned_company_config():
    assert prompts.ticker_for(10456) == "BAX"


def test_ticker_lookup_returns_none_for_a_cik_outside_the_universe():
    assert prompts.ticker_for(999999999) is None


def test_a_segment_label_that_is_only_boilerplate_is_a_hard_error():
    # Carvana and Elanco tag a generic "ReportableSegmentMember", which strips
    # to nothing and renders as "in the  segment".
    with pytest.raises(ValueError):
        prompts.question_text(record(segment_label="Reportable Segment"),
                              ticker="CVNA")


def test_a_restatement_question_asks_for_the_most_recently_reported_figure():
    # Spec 6.1: without this phrase a model answering the superseded figure
    # has a legitimate defense, and a reviewer will say so.
    text = prompts.question_text(
        record(category="restatement", concept="Revenues",
               segment_label=None, segment_axis=None,
               fiscal_period="the fiscal year ended December 31, 2019"),
        ticker="GE",
    )
    assert text.startswith("As most recently reported by")
    assert "revenue" in text.lower()
    assert "the fiscal year ended December 31, 2019" in text


def test_a_non_restatement_question_does_not_say_most_recently_reported():
    text = prompts.question_text(record(), ticker="BAX")
    assert "most recently reported" not in text.lower()


def test_boundary_questions_disambiguate_recast_figures():
    """post_cutoff_boundary gold comes from a filing later than the period, so
    the figure may have been recast since. Round-2 verification found 12 of 98
    boundary records naming a value absent from the company's own as-filed
    filing. Without this phrase a model answering the as-filed figure is scored
    confident-wrong while being defensibly right -- inflating the exact headline
    this benchmark reports.
    """
    record = {
        "company": "HONEYWELL INTERNATIONAL INC",
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "fiscal_period": "the three months ended March 31, 2024",
        "category": "post_cutoff_boundary",
    }
    assert prompts.question_text(record).startswith("As most recently reported by")


def test_boundary_and_restatement_share_one_wording():
    """The phrase is applied to the whole boundary category, not only the
    recast-divergent records. Wording that varied with whether a record happened
    to be recast would make the answer legible from the question -- spec 6.1.
    """
    base = {
        "company": "3M CO",
        "concept": "Revenues",
        "fiscal_period": "the three months ended March 31, 2024",
    }
    boundary = prompts.question_text({**base, "category": "post_cutoff_boundary"})
    restated = prompts.question_text({**base, "category": "restatement"})
    assert boundary == restated

    # ...and a plain answerable question must NOT carry it, or the phrase stops
    # disambiguating anything.
    buried = prompts.question_text({**base, "category": "buried"})
    assert not buried.startswith("As most recently reported")
    assert buried.startswith("What was 3M CO's")
