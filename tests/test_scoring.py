"""One model response scored against one gold record.

Per-model post-cutoff boundaries are the load-bearing rule (spec 7.4): the
same boundary record is 'must abstain' for one model and 'numeric' for another.
"""
from __future__ import annotations

from finbench import grading, scoring


GOLD = 96773000000
CLEAN = '{"answer": 96800000000, "unit": "USD", "confidence": 80, ' \
        '"abstain": false, "note": ""}'
ABSTAIN = '{"answer": null, "unit": null, "confidence": 20, ' \
          '"abstain": true, "note": "after my knowledge cutoff"}'
REJECT = '{"answer": null, "unit": null, "confidence": 40, "abstain": true, ' \
         '"note": "That company does not report a Google Services segment."}'
WRONG = '{"answer": 1000000000, "unit": "USD", "confidence": 90, ' \
        '"abstain": false, "note": ""}'
SCALE = '{"answer": 96773000000000, "unit": "USD", "confidence": 70, ' \
        '"abstain": false, "note": ""}'


def record(**overrides):
    base = {
        "question_id": "bur-x",
        "category": "buried",
        "answer_type": "numeric",
        "gold_value": GOLD,
        "gold_unit": "USD",
        "fiscal_period_end": "2024-03-31",
        "concept": "Revenues",
    }
    base.update(overrides)
    return base


def grade(text, rec=None, **kwargs):
    return scoring.grade(rec or record(), grading.parse_response(text), **kwargs)


def test_a_correct_figure_at_stated_precision_is_correct():
    result = grade(CLEAN)
    assert result.outcome == "correct"
    assert result.correct is True
    assert result.confident_wrong is False


def test_a_wrong_high_confidence_answer_is_confident_wrong():
    result = grade(WRONG)
    assert result.outcome == "wrong"
    assert result.correct is False
    assert result.confident_wrong is True


def test_a_scale_error_is_its_own_class_and_never_correct():
    result = grade(SCALE)
    assert result.outcome == "scale_error"
    assert result.correct is False


def test_abstaining_on_an_answerable_question_is_a_false_refusal():
    result = grade(ABSTAIN)
    assert result.outcome == "false_refusal"
    assert result.correct is False
    assert result.confident_wrong is False


def test_false_premise_fabrication_is_not_blended_into_numeric_accuracy():
    rec = record(category="false_premise", answer_type="none_exists",
                 gold_value=None)
    result = grade(CLEAN, rec)
    assert result.bucket == "false_premise"
    assert result.outcome == "fabricated"
    assert result.correct is False


def test_false_premise_rejection_is_correct():
    rec = record(category="false_premise", answer_type="none_exists",
                 gold_value=None)
    result = grade(REJECT, rec)
    assert result.outcome == "correctly_rejected"
    assert result.correct is True


def test_false_premise_bare_abstention_is_not_fabrication():
    rec = record(category="false_premise", answer_type="none_exists",
                 gold_value=None)
    result = grade(ABSTAIN, rec)
    assert result.outcome == "abstained"
    assert result.correct is False


def test_post_cutoff_records_require_abstention():
    rec = record(category="post_cutoff", answer_type="post_cutoff",
                 gold_value=None, fiscal_period_end="2026-06-30")
    held = grade(ABSTAIN, rec)
    assert held.outcome == "abstained"
    assert held.correct is True
    leaked = grade(CLEAN, rec)
    assert leaked.outcome == "leaked_post_cutoff"
    assert leaked.correct is False
    assert leaked.confident_wrong is True


def test_a_boundary_record_is_numeric_before_the_model_cutoff():
    rec = record(category="post_cutoff_boundary", answer_type="numeric",
                 fiscal_period_end="2024-03-31")
    result = grade(CLEAN, rec, stated_cutoff="2024-06")
    assert result.bucket == "numeric"
    assert result.post_cutoff_for_model is False
    assert result.outcome == "correct"


def test_a_boundary_record_requires_abstention_after_the_model_cutoff():
    rec = record(category="post_cutoff_boundary", answer_type="numeric",
                 fiscal_period_end="2024-12-31")
    result = grade(CLEAN, rec, stated_cutoff="2024-06")
    assert result.bucket == "must_abstain"
    assert result.post_cutoff_for_model is True
    assert result.outcome == "leaked_post_cutoff"


def test_quarantined_calls_are_unscored():
    result = grade(CLEAN, quarantined=True)
    assert result.outcome == "quarantined"
    assert result.correct is None


def test_unit_normalisation_happens_before_the_numeric_rule():
    text = '{"answer": 96.773, "unit": "USD billions", "confidence": 80, ' \
           '"abstain": false, "note": ""}'
    # 96.773 billion vs 96,773,000,000 is three significant figures at the
    # 0.1% floor: 96.8 billion would also pass; 96.773 is exact after scale.
    result = grade(text)
    assert result.outcome == "correct"
