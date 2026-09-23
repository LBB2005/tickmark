"""Score one parsed response against one gold record (spec sections 7.4 and 8).

The numeric rule lives in grading.py and is frozen. This module decides
*which* rule applies for this model: a boundary record is numeric before the
stated cutoff and 'must abstain' after it. Mixing those into one global
post-cutoff set is the comparison spec 7.4 forbids.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from . import grading
from .probe_cutoff import is_post_cutoff

# Default threshold for the headline confident-wrong bit. Analysis reports
# several thresholds; this is the one on the Grade itself.
DEFAULT_CONFIDENT_WRONG = 75


@dataclass
class Grade:
    bucket: str
    outcome: str
    correct: bool | None
    confident_wrong: bool
    post_cutoff_for_model: bool | None
    format_ok: bool
    confidence: int | None
    numeric_class: str | None
    false_premise_class: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bucket(record: dict[str, Any], stated_cutoff: str | None) -> tuple[str, bool | None]:
    """Which scoring regime this record uses for this model's cutoff."""
    if record.get("answer_type") == "none_exists" or record.get("category") == "false_premise":
        return "false_premise", None
    if record.get("answer_type") == "post_cutoff":
        return "must_abstain", True
    if record.get("category") == "post_cutoff_boundary":
        post = is_post_cutoff(record["fiscal_period_end"], stated_cutoff)
        if post is True:
            return "must_abstain", True
        if post is False:
            return "numeric", False
        # Unknown cutoff: refuse to guess. The caller must treat this as
        # unscored rather than silently dropping the record into numeric.
        return "cutoff_unknown", None
    return "numeric", None


def grade(
    record: dict[str, Any],
    parsed: grading.Parsed,
    *,
    stated_cutoff: str | None = None,
    quarantined: bool = False,
    confidence_threshold: int = DEFAULT_CONFIDENT_WRONG,
) -> Grade:
    """Apply the frozen rules under the right per-model bucket."""
    if quarantined:
        return Grade(
            bucket="unscored", outcome="quarantined", correct=None,
            confident_wrong=False, post_cutoff_for_model=None,
            format_ok=parsed.format_ok, confidence=parsed.confidence,
            numeric_class=None, false_premise_class=None,
        )

    bucket, post = _bucket(record, stated_cutoff)
    abstained = grading.is_abstention(parsed)
    confidence = parsed.confidence
    high = confidence is not None and confidence >= confidence_threshold

    if bucket == "false_premise":
        fp = grading.classify_false_premise(parsed)
        return Grade(
            bucket=bucket, outcome=fp,
            correct=(fp == "correctly_rejected"),
            confident_wrong=(fp == "fabricated" and high),
            post_cutoff_for_model=post, format_ok=parsed.format_ok,
            confidence=confidence, numeric_class=None, false_premise_class=fp,
        )

    if bucket == "must_abstain":
        if abstained:
            return Grade(
                bucket=bucket, outcome="abstained", correct=True,
                confident_wrong=False, post_cutoff_for_model=post,
                format_ok=parsed.format_ok, confidence=confidence,
                numeric_class=None, false_premise_class=None,
            )
        return Grade(
            bucket=bucket, outcome="leaked_post_cutoff", correct=False,
            confident_wrong=high, post_cutoff_for_model=post,
            format_ok=parsed.format_ok, confidence=confidence,
            numeric_class=None, false_premise_class=None,
        )

    if bucket == "cutoff_unknown":
        return Grade(
            bucket=bucket, outcome="unscored", correct=None,
            confident_wrong=False, post_cutoff_for_model=None,
            format_ok=parsed.format_ok, confidence=confidence,
            numeric_class=None, false_premise_class=None,
        )

    # Numeric / answerable.
    if abstained or parsed.answer is None:
        return Grade(
            bucket="numeric", outcome="false_refusal", correct=False,
            confident_wrong=False, post_cutoff_for_model=post,
            format_ok=parsed.format_ok, confidence=confidence,
            numeric_class=None, false_premise_class=None,
        )

    value = grading.normalise(parsed.answer, parsed.unit)
    klass = grading.classify_numeric(value, float(record["gold_value"]))
    return Grade(
        bucket="numeric", outcome=klass, correct=(klass == "correct"),
        confident_wrong=(klass != "correct" and high),
        post_cutoff_for_model=post, format_ok=parsed.format_ok,
        confidence=confidence, numeric_class=klass, false_premise_class=None,
    )
