"""Gold record schema (spec section 5.4), with validation.

answer_type is first-class. Roughly a third of the set has "the correct answer
is that there is no answer" - encoding that as a null gold_value would make
"no such segment exists" indistinguishable from "we failed to extract the
number", and would silently corrupt the false-premise and post-cutoff
categories. The validator enforces the distinction in both directions: a
numeric record must carry a value, and a none_exists record must not.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any, Iterable

ANSWER_TYPES = {"numeric", "text", "none_exists", "post_cutoff"}
CATEGORIES = {"buried", "restatement", "post_cutoff", "post_cutoff_boundary",
              "false_premise", "covenant"}
DIFFICULTIES = {"headline", "mid", "deep", None}
VERIFICATIONS = {"auto", "human"}

REQUIRED = [
    "question_id", "company", "cik", "fiscal_period", "fiscal_period_end",
    "concept", "answer_type", "gold_value", "gold_unit", "superseded_value",
    "source_accession", "source_form", "source_filed_date", "source_url",
    "category", "difficulty", "verification", "verified_by", "verified_date",
]

VALUE_BEARING = {"numeric", "text"}


def validate(record: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED if field not in record]
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")

    answer_type = record["answer_type"]
    if answer_type not in ANSWER_TYPES:
        raise ValueError(f"bad answer_type: {answer_type!r}")
    if record["category"] not in CATEGORIES:
        raise ValueError(f"bad category: {record['category']!r}")
    if record["difficulty"] not in DIFFICULTIES:
        raise ValueError(f"bad difficulty: {record['difficulty']!r}")
    if record["verification"] not in VERIFICATIONS:
        raise ValueError(f"bad verification: {record['verification']!r}")

    has_value = record["gold_value"] is not None
    if answer_type in VALUE_BEARING and not has_value:
        raise ValueError(f"answer_type {answer_type} requires a gold_value")
    if answer_type not in VALUE_BEARING and has_value:
        raise ValueError(f"answer_type {answer_type} must have a null gold_value")
    return record


def write(records: Iterable[dict[str, Any]], path: pathlib.Path) -> int:
    records = list(records)
    seen: set[str] = set()
    for record in records:
        validate(record)
        if record["question_id"] in seen:
            raise ValueError(f"duplicate question_id: {record['question_id']}")
        seen.add(record["question_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(records)


def read(path: pathlib.Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
