"""Automated pre-check for false-premise records.

A false-premise question is only correct if the segment it names genuinely does
not exist for that company in that period. If it does exist, the record's
"correct" answer silently inverts and the category is corrupted - the exact
failure mode spec section 6.5 calls out as happening constantly with recast
segments.

This cannot replace the human pass, because absence from our corpus is not the
same as absence from the filings. What it does is separate the records where
absence is positively confirmed from the handful where it cannot be, so the
human pass is spent on the ones that actually carry risk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import dimensional

MIN_SUBSTRING_LEN = 8


def normalise(name: str) -> str:
    """Strip segment/member boilerplate and punctuation for comparison.

    Boilerplate is removed AFTER collapsing to bare alphanumerics, because the
    two naming styles differ: filings label members "Med Tech Segment" while
    the element is "MedTechMember", and a word-boundary regex cannot see the
    suffix in the camel-case form.
    """
    collapsed = re.sub(r"[^a-z0-9]", "", name.lower())
    for boilerplate in ("reportable", "segments", "segment", "member"):
        collapsed = collapsed.replace(boilerplate, "")
    return collapsed


def matches(candidate: str, member: str) -> bool:
    """Whether a claimed-absent segment collides with a real member.

    Substring matching needs a length floor on BOTH sides. Without it the
    geographic member "US" matches inside "SafetyAndIndustrial" and every long
    segment name looks like a collision.
    """
    a, b = normalise(candidate), normalise(member)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= MIN_SUBSTRING_LEN and len(b) >= MIN_SUBSTRING_LEN:
        return a in b or b in a
    return False


@dataclass(frozen=True)
class PreCheck:
    question_id: str
    status: str          # absent_confirmed | collision | no_segment_data
    detail: str


def members_by_cik(facts: list[dimensional.SegmentFact] | None = None
                   ) -> dict[int, set[str]]:
    facts = dimensional.load_cached() if facts is None else facts
    out: dict[int, set[str]] = {}
    for fact in facts:
        if fact.axis != dimensional.SEGMENT_AXIS:
            continue
        out.setdefault(fact.cik, set()).update({fact.member, fact.member_label})
    return out


def check(records: list[dict], facts: list[dimensional.SegmentFact] | None = None
          ) -> list[PreCheck]:
    owned = members_by_cik(facts)
    results: list[PreCheck] = []
    for record in records:
        if record.get("category") != "false_premise":
            continue
        claimed = record.get("nonexistent_segment", "")
        members = owned.get(record["cik"])
        if not members:
            results.append(PreCheck(record["question_id"], "no_segment_data",
                                    "no business-segment facts for this company"))
            continue
        hits = sorted({m for m in members if matches(claimed, m)})
        if hits:
            results.append(PreCheck(record["question_id"], "collision",
                                    f"resembles real member(s): {', '.join(hits[:3])}"))
        else:
            results.append(PreCheck(record["question_id"], "absent_confirmed",
                                    f"absent from {len(members)} known members"))
    return results
