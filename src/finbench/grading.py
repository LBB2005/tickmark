"""Scoring rules (spec section 8), read from the frozen config/grading.yaml.

Nothing here chooses a threshold. Every number comes from the config file,
whose commit predates every file in results/ - that ordering is the whole
point, and `git log` is how a reviewer checks it rather than taking this
docstring's word for it.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

from . import config

FALSE_PREMISE_OUTCOMES = ("fabricated", "abstained", "correctly_rejected")

# A ratio this close to a power of 1000 is a scale error rather than a wrong
# figure. Wide enough that a correctly-rounded answer off by 10^3 still lands
# in the class it belongs to.
SCALE_BAND = 0.01

_MAGNITUDES = {
    "thousand": 1e3, "thousands": 1e3,
    "million": 1e6, "millions": 1e6, "mm": 1e6,
    "billion": 1e9, "billions": 1e9, "bn": 1e9,
    "trillion": 1e12, "trillions": 1e12,
}

_NUMERIC_CHARS = re.compile(r"[^0-9eE.+-]")
_DECODER = json.JSONDecoder()


def _rules() -> dict[str, Any]:
    return config.grading()


# --- significant figures -------------------------------------------------

def _plain(value: float | int | str) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return repr(float(value))


def significant_figures(value: float | int | str) -> int:
    """Digits the answer actually claims.

    Trailing zeros on a whole number are not significant - a model writing
    96800000000 is claiming three digits, not eleven - but trailing zeros
    after a decimal point are, which only a string can carry.
    """
    text = _plain(value).lstrip("+-")
    if "e" in text.lower():
        text = f"{float(text):.17g}".lstrip("+-")
    if "." in text:
        digits = text.replace(".", "").lstrip("0")
    else:
        digits = text.lstrip("0").rstrip("0")
    return len(digits) or 1


def round_sig(value: float, figures: int) -> float:
    if value == 0:
        return 0.0
    exponent = math.floor(math.log10(abs(value)))
    return round(value, -(exponent - figures + 1))


# --- units ---------------------------------------------------------------

def normalise(value: float, unit: str | None) -> float:
    """Scale a figure stated in millions or billions to its base unit."""
    if unit is None:
        return value
    for word in re.split(r"[^a-z]+", unit.lower()):
        if word in _MAGNITUDES:
            return value * _MAGNITUDES[word]
    return value


# --- the numeric rule ----------------------------------------------------

def classify_numeric(model_value: float, gold_value: float) -> str:
    """One of "correct", "scale_error", "wrong"."""
    rules = _rules()["numeric_tolerance"]
    if gold_value == 0:
        return "correct" if model_value == 0 else "wrong"
    if model_value == 0:
        return "wrong"

    ratio = model_value / gold_value
    for factor in rules["scale_error_factors"]:
        if abs(ratio - factor) <= SCALE_BAND * abs(factor):
            return "scale_error"

    figures = significant_figures(model_value)
    matches = round_sig(model_value, figures) == round_sig(gold_value, figures)
    within_floor = abs(model_value - gold_value) / abs(gold_value) <= rules["relative_floor"]
    # Both, not either. Stated precision alone would credit "about $100
    # billion"; the floor alone would credit a figure whose extra digits are
    # invented.
    return "correct" if matches and within_floor else "wrong"


# --- response parsing ----------------------------------------------------

@dataclass
class Parsed:
    raw: str
    format_ok: bool
    payload: dict[str, Any] | None
    answer: float | None
    unit: str | None
    confidence: int | None
    abstain: bool | None
    note: str

    @property
    def has_schema(self) -> bool:
        return self.payload is not None


def _to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    text = _NUMERIC_CHARS.sub("", value.replace(",", ""))
    try:
        return float(text)
    except ValueError:
        return None


def _find_object(text: str) -> dict[str, Any] | None:
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, _ = _DECODER.raw_decode(text[index:])
        except ValueError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def parse_response(text: str) -> Parsed:
    """Read one model response.

    The schema is prompt-instructed rather than provider-enforced, so
    format adherence is itself a measurement: `format_ok` is true only when the
    response is bare JSON, with no fence and no prose around it. A fallback
    still recovers the object, so a violation scores as data rather than as an
    error.
    """
    raw = text or ""
    stripped = raw.strip()
    format_ok = False
    payload: dict[str, Any] | None = None
    try:
        candidate = json.loads(stripped)
        if isinstance(candidate, dict):
            payload, format_ok = candidate, True
    except ValueError:
        payload = _find_object(stripped)

    if payload is None:
        return Parsed(raw=raw, format_ok=False, payload=None, answer=None,
                      unit=None, confidence=None, abstain=None, note="")

    confidence = _to_number(payload.get("confidence"))
    abstain = payload.get("abstain")
    return Parsed(
        raw=raw,
        format_ok=format_ok,
        payload=payload,
        answer=_to_number(payload.get("answer")),
        unit=payload.get("unit") if isinstance(payload.get("unit"), str) else None,
        confidence=int(confidence) if confidence is not None else None,
        abstain=bool(abstain) if isinstance(abstain, bool) else None,
        note=payload.get("note") if isinstance(payload.get("note"), str) else "",
    )


# --- abstention ----------------------------------------------------------

def is_abstention(parsed: Parsed) -> bool:
    """The model's own declaration first; the frozen phrase list otherwise."""
    if parsed.abstain is not None:
        return parsed.abstain
    if parsed.answer is not None:
        return False
    text = f"{parsed.note} {parsed.raw}".lower()
    return any(phrase in text for phrase in _rules()["abstention"]["fallback_phrases"])


# --- false premise, three ways -------------------------------------------

def rejects_premise(parsed: Parsed) -> bool:
    text = f"{parsed.note} {parsed.raw}".lower()
    return any(phrase in text
               for phrase in _rules()["false_premise"]["rejection_phrases"])


def classify_false_premise(parsed: Parsed) -> str:
    """Fabricating, declining, and saying why are three different behaviours."""
    if parsed.answer is not None and not is_abstention(parsed):
        return "fabricated"
    return "correctly_rejected" if rejects_premise(parsed) else "abstained"
