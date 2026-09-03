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

from . import config, edgar, observations, restatements
from .http import SecClient

MIN_RESTATEMENTS = 3     # roles A, D - the restatement engine
MIN_SEGMENT_MEMBERS = 4  # roles C, F, G - dimensional richness

FIELDS = ["ticker", "cik", "name", "role", "n_concepts", "n_restatements",
          "n_segment_members", "public_float", "verdict"]


def verdict(role: str, *, n_restatements: int,
            n_segment_members: int | None) -> str:
    """Role-aware keep/drop. n_segment_members=None means "not computed yet".

    Roles C/F/G are judged entirely on segment richness, so before the
    dimensional source exists (Task 1.5) their verdict is PENDING, not THIN.
    Writing THIN there would put 21 false negatives in screen.csv and would
    look like a finding rather than an unfinished pipeline.
    """
    if role in ("A", "D"):
        return "KEEP" if n_restatements >= MIN_RESTATEMENTS else "THIN"
    if role in ("C", "F", "G"):
        if n_segment_members is None:
            return "PENDING"
        return "KEEP" if n_segment_members >= MIN_SEGMENT_MEMBERS else "THIN"
    # B (short-history spin-offs) are wanted precisely because they are thin;
    # E (share structure) is judged on cover-page share classes, not here.
    return "KEEP"


def score(*, ticker: str, cik: int, name: str, role: str, facts: dict,
          segment_members: int | None) -> dict[str, Any]:
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
        "public_float": observations.public_float(facts),
        "verdict": verdict(role, n_restatements=len(found),
                           n_segment_members=segment_members),
    }


def run(out_path: pathlib.Path | None = None) -> list[dict[str, Any]]:
    config.load_dotenv()
    out_path = out_path or config.DATA_DIR / "screen.csv"
    rows: list[dict[str, Any]] = []
    with SecClient() as client:
        for entry in config.companies()["companies"]:
            try:
                facts = edgar.fetch_companyfacts(client, entry["cik"])
            except Exception as exc:  # noqa: BLE001
                print(f"  {entry['ticker']:<6} FETCH FAILED: {exc}")
                continue
            row = score(ticker=entry["ticker"], cik=entry["cik"], name=entry["name"],
                        role=entry["role"], facts=facts, segment_members=None)
            rows.append(row)
            float_str = f"{row['public_float']/1e9:>7.1f}B" if row["public_float"] else "      -"
            print(f"  {row['ticker']:<6} {row['role']:<3} "
                  f"restated={row['n_restatements']:<5} "
                  f"concepts={row['n_concepts']:<5} float={float_str}  {row['verdict']}")

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
