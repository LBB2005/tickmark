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
