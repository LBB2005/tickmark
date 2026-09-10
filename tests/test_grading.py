"""Scoring rules, frozen in config/grading.yaml before any model was called."""
from __future__ import annotations

import pytest

from finbench import grading


# --- significant figures -------------------------------------------------

def test_trailing_zeros_are_not_significant():
    assert grading.significant_figures(96800000000) == 3


def test_every_digit_of_an_exact_looking_figure_counts():
    assert grading.significant_figures(96773000000) == 5


def test_decimals_keep_their_trailing_zeros():
    # Only a string can carry them: the float 4.50 IS 4.5.
    assert grading.significant_figures("4.50") == 3
    assert grading.significant_figures(4.5) == 2


def test_leading_zeros_are_not_significant():
    assert grading.significant_figures(0.0042) == 2


# --- the numeric rule ----------------------------------------------------

GOLD = 96773000000


def test_correct_at_the_precision_the_model_stated():
    assert grading.classify_numeric(96800000000, GOLD) == "correct"


def test_an_exact_match_is_correct():
    assert grading.classify_numeric(GOLD, GOLD) == "correct"


def test_a_one_sig_fig_answer_fails_the_relative_floor():
    # "about $100 billion" rounds to the same 1 s.f. as gold. The 0.1% floor
    # is what stops it scoring as correct.
    assert grading.classify_numeric(100000000000, GOLD) == "wrong"


def test_more_digits_than_the_gold_value_are_graded_against_them():
    assert grading.classify_numeric(96773412000, GOLD) == "wrong"


def test_a_thousandfold_answer_is_a_scale_error_not_a_wrong_figure():
    assert grading.classify_numeric(GOLD * 1000, GOLD) == "scale_error"
    assert grading.classify_numeric(GOLD / 1000, GOLD) == "scale_error"


def test_a_scale_error_is_never_correct_even_at_coarse_precision():
    assert grading.classify_numeric(96800000000000, GOLD) == "scale_error"


def test_a_genuinely_different_figure_is_wrong():
    assert grading.classify_numeric(88400000000, GOLD) == "wrong"


def test_sign_matters():
    assert grading.classify_numeric(4.99, -4.99) == "wrong"


def test_a_zero_gold_value_does_not_divide_by_zero():
    assert grading.classify_numeric(0, 0) == "correct"
    assert grading.classify_numeric(1000, 0) == "wrong"


# --- unit normalisation --------------------------------------------------

def test_a_figure_stated_in_millions_is_scaled_before_comparison():
    assert grading.normalise(96773, "USD millions") == 96773000000


def test_a_plain_currency_unit_is_left_alone():
    assert grading.normalise(96773000000, "USD") == 96773000000


def test_units_are_case_and_spacing_insensitive():
    assert grading.normalise(1.5, "usd  Billions") == 1500000000


# --- response parsing ----------------------------------------------------

CLEAN = '{"answer": 96800000000, "unit": "USD", "confidence": 70, ' \
        '"abstain": false, "note": ""}'


def test_a_clean_json_response_parses_and_counts_as_format_adherent():
    parsed = grading.parse_response(CLEAN)
    assert parsed.format_ok
    assert parsed.answer == 96800000000
    assert parsed.confidence == 70
    assert parsed.abstain is False


def test_a_fenced_json_response_parses_but_is_not_format_adherent():
    parsed = grading.parse_response(f"```json\n{CLEAN}\n```")
    assert parsed.answer == 96800000000
    assert not parsed.format_ok


def test_json_with_prose_around_it_still_yields_the_object():
    parsed = grading.parse_response(f"Sure - here you go:\n{CLEAN}\nHope that helps.")
    assert parsed.answer == 96800000000
    assert not parsed.format_ok


def test_a_prose_only_response_parses_to_no_answer():
    parsed = grading.parse_response("I don't have that figure to hand.")
    assert parsed.answer is None
    assert not parsed.format_ok
    assert parsed.raw.startswith("I don't have")


def test_a_number_written_with_separators_or_a_currency_sign_is_read():
    parsed = grading.parse_response('{"answer": "$96,800,000,000", "unit": "USD", '
                                    '"confidence": 70, "abstain": false, "note": ""}')
    assert parsed.answer == 96800000000


# --- abstention ----------------------------------------------------------

def test_the_abstain_field_decides_when_it_is_present():
    parsed = grading.parse_response('{"answer": null, "unit": null, '
                                    '"confidence": 0, "abstain": true, "note": ""}')
    assert grading.is_abstention(parsed)


def test_prose_falls_back_to_the_frozen_phrase_list():
    assert grading.is_abstention(grading.parse_response(
        "I do not have reliable data for that period."))


def test_a_confident_prose_answer_is_not_an_abstention():
    assert not grading.is_abstention(grading.parse_response(
        "Revenue was approximately 96.8 billion dollars."))


def test_an_answer_given_alongside_abstain_true_is_still_an_abstention():
    # The field is the model's own declaration; honour it.
    parsed = grading.parse_response('{"answer": 5, "unit": "USD", '
                                    '"confidence": 10, "abstain": true, "note": ""}')
    assert grading.is_abstention(parsed)


# --- false premise, three ways -------------------------------------------

def test_a_figure_for_a_segment_that_does_not_exist_is_fabrication():
    assert grading.classify_false_premise(grading.parse_response(CLEAN)) == "fabricated"


def test_naming_the_missing_segment_in_the_note_is_a_correct_rejection():
    parsed = grading.parse_response(
        '{"answer": null, "unit": null, "confidence": 0, "abstain": true, '
        '"note": "That company does not report a Google Services segment."}')
    assert grading.classify_false_premise(parsed) == "correctly_rejected"


def test_declining_without_saying_why_is_only_an_abstention():
    parsed = grading.parse_response(
        '{"answer": null, "unit": null, "confidence": 0, "abstain": true, '
        '"note": "I am not able to recall this figure."}')
    assert grading.classify_false_premise(parsed) == "abstained"


def test_rejecting_the_premise_in_prose_without_the_schema_still_counts():
    parsed = grading.parse_response(
        "There is no such segment - the company does not report one by that name.")
    assert grading.classify_false_premise(parsed) == "correctly_rejected"


def test_the_three_outcomes_are_exactly_the_frozen_ones():
    assert set(grading.FALSE_PREMISE_OUTCOMES) == {
        "fabricated", "abstained", "correctly_rejected"}
