"""Headline rates computed from scored rows, not from live model calls."""
from __future__ import annotations

from finbench import analyze


def row(**overrides):
    base = {
        "model_id": "aa",
        "question_id": "q1",
        "sample_idx": 0,
        "category": "buried",
        "difficulty": "mid",
        "role": "flagship",
        "outcome": "correct",
        "bucket": "numeric",
        "correct": True,
        "confident_wrong": False,
        "format_ok": True,
        "confidence": 80,
        "quarantined": False,
    }
    base.update(overrides)
    return base


def test_confident_wrong_rate_is_a_proportion_with_an_interval():
    rows = [
        row(question_id="a", confident_wrong=True, correct=False, outcome="wrong"),
        row(question_id="b", confident_wrong=False),
        row(question_id="c", confident_wrong=True, correct=False, outcome="wrong"),
        row(question_id="d", confident_wrong=False),
    ]
    summary = analyze.summarise(rows)
    rate = summary["models"]["aa"]["confident_wrong"]
    assert rate["k"] == 2
    assert rate["n"] == 4
    assert abs(rate["point"] - 0.5) < 1e-9
    assert rate["low"] < 0.5 < rate["high"]


def test_fabrication_rate_uses_only_false_premise_rows():
    rows = [
        row(category="false_premise", bucket="false_premise",
            outcome="fabricated", correct=False),
        row(category="false_premise", question_id="q2", bucket="false_premise",
            outcome="correctly_rejected", correct=True, confident_wrong=False),
        row(category="buried", question_id="q3"),
    ]
    summary = analyze.summarise(rows)
    fab = summary["models"]["aa"]["fabrication"]
    assert fab["k"] == 1 and fab["n"] == 2


def test_quarantined_rows_are_dropped_from_rates():
    rows = [
        row(quarantined=True, correct=None, outcome="quarantined"),
        row(question_id="q2"),
    ]
    summary = analyze.summarise(rows)
    assert summary["models"]["aa"]["confident_wrong"]["n"] == 1


def test_brier_is_zero_when_confidence_matches_outcomes():
    rows = [
        row(confidence=100, correct=True),
        row(question_id="q2", confidence=0, correct=False, outcome="wrong"),
    ]
    summary = analyze.summarise(rows)
    assert summary["models"]["aa"]["brier"] == 0.0


def test_confidence_auc_is_one_when_every_correct_is_more_sure():
    rows = [
        row(confidence=90, correct=True),
        row(question_id="q2", confidence=10, correct=False, outcome="wrong"),
    ]
    summary = analyze.summarise(rows)
    assert summary["models"]["aa"]["confidence_auc"] == 1.0


def test_a_recovered_retry_counts_once_and_is_reported():
    rows = [
        row(ok=False, quarantined=True, correct=None, outcome="quarantined",
            attempt=1),
        row(ok=True, attempt=2),
    ]
    block = analyze.summarise(rows)["models"]["aa"]
    assert block["n"] == 1
    assert block["retried"] == 1
    assert block["still_failed"] == 0
    # A timeout that later succeeded is not a quarantine.
    assert block["quarantined"] == 0


def test_a_cell_that_never_succeeded_is_still_failed_not_silent():
    rows = [
        row(ok=False, quarantined=True, correct=None, outcome="quarantined", attempt=1),
        row(ok=False, quarantined=True, correct=None, outcome="quarantined", attempt=2),
        row(question_id="q2"),
    ]
    block = analyze.summarise(rows)["models"]["aa"]
    assert block["n"] == 1
    assert block["still_failed"] == 1


def test_toggle_rows_never_reach_the_headline_table():
    rows = [
        row(question_id="q1"),
        row(question_id="q1", track="reasoning_toggle", arm="on",
            confident_wrong=True, correct=False, outcome="wrong"),
    ]
    summary = analyze.summarise(rows)
    block = summary["models"]["aa"]
    assert block["n"] == 1
    assert block["confident_wrong"]["k"] == 0


def test_toggle_pairs_on_arm_with_main_run_off_arm_on_same_cells():
    rows = [
        # main run: three questions, only q1 and q2 are in the toggle subset
        row(model_id="claude-opus-5", question_id="q1", correct=False,
            outcome="wrong", confident_wrong=True),
        row(model_id="claude-opus-5", question_id="q2"),
        row(model_id="claude-opus-5", question_id="q3"),
        row(model_id="gpt", question_id="q1"),
        # toggle on-arm
        row(model_id="claude-opus-5", question_id="q1", track="reasoning_toggle",
            arm="on"),
        row(model_id="claude-opus-5", question_id="q2", track="reasoning_toggle",
            arm="on", correct=False, outcome="wrong"),
    ]
    toggle = analyze.summarise_toggle(rows, model_id="claude-opus-5")
    assert toggle["off"]["n"] == 2          # q3 and the other model excluded
    assert toggle["on"]["n"] == 2
    assert toggle["off"]["confident_wrong"]["k"] == 1
    assert toggle["on"]["confident_wrong"]["k"] == 0
    assert toggle["paired_cells"] == 2
    assert toggle["flips"] == {"wrong_to_right": 1, "right_to_wrong": 1}


def test_no_toggle_rows_means_no_toggle_section():
    assert analyze.summarise_toggle([row()], model_id="claude-opus-5") is None


def test_credit_exhaustion_is_not_counted_as_a_retry():
    # 402s are an account problem, not a measurement event. A cell that hit a
    # 402 and then succeeded on --resume was never "retried" in the sense the
    # Coverage section reports.
    rows = [
        row(ok=False, quarantined=True, correct=None, outcome="quarantined",
            attempt=1, error='402: {"error":{"message":"exceed your available credits"}}'),
        row(ok=True, attempt=2),
    ]
    block = analyze.summarise(rows)["models"]["aa"]
    assert block["n"] == 1
    assert block["retried"] == 0
    assert block["still_failed"] == 0
