"""Write completed verification results back into gold.jsonl.

Records confirmed by a human get verification=human plus who and when. Records
marked wrong are REMOVED from the gold set and written to gold_rejected.jsonl
with the reason, never silently corrected - a record that failed verification
is evidence about the pipeline and belongs in the methodology, not in a diff.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys

from finbench import gold
from finbench.config import DATA_DIR


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    verifier = argv[0] if argv else os.environ.get("USER", "unknown")
    today = dt.date.today().isoformat()

    sheet_path = DATA_DIR / "verification_sheet.csv"
    if not sheet_path.exists():
        print(f"no sheet at {sheet_path}; run build_verification_sheet.py first",
              file=sys.stderr)
        return 1

    with sheet_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    passed, failed, blank = {}, {}, 0
    for row in rows:
        answer = (row.get("verified_ok") or "").strip().lower()
        if answer in ("y", "yes", "1", "true"):
            passed[row["question_id"]] = row
        elif answer in ("n", "no", "0", "false"):
            failed[row["question_id"]] = row
        else:
            blank += 1

    if blank:
        print(f"WARNING: {blank} rows still blank; they stay verification=auto")

    records = gold.read(DATA_DIR / "gold.jsonl")
    kept, rejected = [], []
    for record in records:
        qid = record["question_id"]
        if qid in failed:
            row = failed[qid]
            rejected.append({**record,
                             "rejected_reason": row.get("notes") or "failed human verification",
                             "observed_value": row.get("actual_value_if_wrong") or None,
                             "rejected_by": verifier, "rejected_date": today})
            continue
        if qid in passed:
            record = {**record, "verification": "human",
                      "verified_by": verifier, "verified_date": today}
        kept.append(record)

    gold.write(kept, DATA_DIR / "gold.jsonl")
    if rejected:
        with (DATA_DIR / "gold_rejected.jsonl").open("w", encoding="utf-8") as fh:
            for record in rejected:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    human = sum(1 for r in kept if r["verification"] == "human")
    checked = len(passed) + len(failed)
    rate = (len(passed) / checked * 100) if checked else 0.0
    print(f"kept {len(kept)}  rejected {len(rejected)}  human-verified {human}")
    print(f"verification pass rate: {len(passed)}/{checked} ({rate:.1f}%)")
    if rejected:
        print(f"rejected records -> {DATA_DIR / 'gold_rejected.jsonl'}")
        for record in rejected[:10]:
            print(f"  {record['question_id']:<28} {record['rejected_reason'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
