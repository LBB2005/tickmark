"""Density screen - build this first (spec section 5.1).

The role letters in the spec are hypotheses. This confirms or kills them
before a single question is written, and doubles as the end-to-end test of the
EDGAR pull.

The verdict is role-aware on purpose: a recast-heavy parent is thin if it has
no restatements even when its segment disclosure is rich, and a multi-segment
reporter is thin the other way round. One global threshold would keep the
wrong companies.
"""
from __future__ import annotations

import csv
import pathlib
from typing import Any

from . import config, dimensional, edgar, observations, restatements
from .http import SecClient

MIN_RESTATEMENTS = 3  # roles A, D - the restatement engine

# Buried-but-knowable questions each role must supply, taken straight from the
# spec's section 6.4 supply table ("C (4 ea), A (2 ea), F/D (2 ea), G (1 ea)").
# The screen asks exactly one question - can this company supply its share? -
# rather than applying a threshold picked to produce a pleasing answer.
#
# The measure is usable segment-revenue FACTS, not distinct segment members.
# Amazon reports three segments and reports them every quarter; counting
# members would call it thin while it can in fact supply many questions.
MIN_SEGMENT_FACTS = {"C": 4, "F": 2, "G": 1}

FIELDS = ["ticker", "cik", "name", "role", "n_concepts", "n_restatements",
          "n_segment_members", "n_segment_facts", "public_float", "verdict"]


def verdict(role: str, *, n_restatements: int,
            n_segment_facts: int | None) -> str:
    """Role-aware keep/drop. n_segment_facts=None means "not computed yet".

    Roles C/F/G are judged entirely on segment supply, so before the
    dimensional source exists their verdict is PENDING, not THIN. Writing THIN
    there would put false negatives in screen.csv and would look like a
    finding rather than an unfinished pipeline.
    """
    if role in ("A", "D"):
        return "KEEP" if n_restatements >= MIN_RESTATEMENTS else "THIN"
    if role in MIN_SEGMENT_FACTS:
        if n_segment_facts is None:
            return "PENDING"
        return "KEEP" if n_segment_facts >= MIN_SEGMENT_FACTS[role] else "THIN"
    # B (short-history spin-offs) are wanted precisely because they are thin;
    # E (share structure) is judged on cover-page share classes, not here.
    return "KEEP"


def score(*, ticker: str, cik: int, name: str, role: str, facts: dict,
          segment_members: int | None, segment_facts: int | None = None) -> dict[str, Any]:
    found = restatements.find(facts)
    concepts = {o.concept for o in observations.iter_observations(facts)}
    return {
        "ticker": ticker,
        "cik": cik,
        "name": name,
        "role": role,
        "n_concepts": len(concepts),
        "n_restatements": len(found),
        "n_segment_members": segment_members,
        "n_segment_facts": segment_facts,
        "public_float": observations.public_float(facts),
        "verdict": verdict(role, n_restatements=len(found),
                           n_segment_facts=segment_facts),
    }


def run(out_path: pathlib.Path | None = None) -> list[dict[str, Any]]:
    config.load_dotenv()
    out_path = out_path or config.DATA_DIR / "screen.csv"
    segments = dimensional.load_cached()
    by_cik: dict[int, set[str]] = {}
    facts_by_cik: dict[int, set[tuple]] = {}
    for fact in segments:
        if fact.concept not in dimensional.REVENUE_TAGS:
            continue
        if fact.axis == dimensional.SEGMENT_AXIS:
            by_cik.setdefault(fact.cik, set()).add(fact.member)
        # One distinct fact = one candidate question.
        facts_by_cik.setdefault(fact.cik, set()).add(
            (fact.axis, fact.member, fact.concept, fact.end, fact.qtrs))
    if not segments:
        print("WARNING: no segment cache; roles C/F/G will stay PENDING")
    rows: list[dict[str, Any]] = []
    with SecClient() as client:
        for entry in config.companies()["companies"]:
            try:
                facts = edgar.fetch_companyfacts(client, entry["cik"])
            except Exception as exc:  # noqa: BLE001
                print(f"  {entry['ticker']:<6} FETCH FAILED: {exc}")
                continue
            row = score(ticker=entry["ticker"], cik=entry["cik"], name=entry["name"],
                        role=entry["role"], facts=facts,
                        segment_members=len(by_cik.get(entry["cik"], ()))
                        if segments else None,
                        segment_facts=len(facts_by_cik.get(entry["cik"], ()))
                        if segments else None)
            rows.append(row)
            print(f"  {row['ticker']:<6} {row['role']:<3} "
                  f"restated={row['n_restatements']:<5} "
                  f"seg={str(row['n_segment_members']):<3} "
                  f"segfacts={str(row['n_segment_facts']):<5} {row['verdict']}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    thin = [r["ticker"] for r in rows if r["verdict"] == "THIN"]
    pending = [r["ticker"] for r in rows if r["verdict"] == "PENDING"]
    print(f"\n{len(rows)} scored -> {out_path}")
    print(f"THIN ({len(thin)}): {', '.join(thin) or 'none'}")
    if pending:
        print(f"PENDING segment data ({len(pending)}): {', '.join(pending)}")
    return rows


if __name__ == "__main__":
    run()
