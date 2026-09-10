"""Build the human verification worksheet (spec section 5.5, plan Task 1.9).

The script proposes; a human confirms against the actual filing page. This
produces the list to work through and the exact URL for each item, so the pass
is clicking and ticking rather than assembling a list by hand.

Sampling follows the plan:
  * EVERY false-premise record. A "false" premise that turns out to be true is
    not a near miss, it silently inverts that record's correct answer and
    corrupts the category.
  * EVERY covenant record, which is hand-sourced prose to begin with.
  * A seeded random sample of everything else, so the draw is reproducible and
    cannot be quietly redrawn after seeing results.
"""
from __future__ import annotations

import csv
import random

from finbench import false_premise, gold, prompts
from finbench.config import DATA_DIR

SEED = 20260902
SAMPLE_OTHERS = 40

CHECK = {
    "false_premise": ("Open the company's latest 10-K segment footnote. CONFIRM "
                      "the named segment does NOT exist for this company in this "
                      "period. If it does exist, the record is broken - mark n."),
    "covenant": ("Open the credit agreement exhibit. Confirm the covenant term "
                 "and threshold match the gold value verbatim."),
    "restatement": ("Open BOTH filings. Confirm the superseded value appears in "
                    "the earlier one and the gold value in the later one, for "
                    "the same period."),
    "buried": ("Open the filing. Confirm the gold value appears for this "
               "concept and period, in the stated unit."),
    "post_cutoff_boundary": ("Open the filing. Confirm the gold value appears "
                             "for this concept and period. Whether abstention "
                             "or the figure is correct is decided per model "
                             "from the measured cutoffs, not here."),
    "post_cutoff": ("Confirm the filing covers this period and was filed on the "
                    "stated date. The correct model behaviour is abstention, so "
                    "gold_value is intentionally null."),
}

FIELDS = ["priority", "precheck", "verified_ok", "actual_value_if_wrong",
          "notes", "question_id", "question",
          "category", "company", "concept", "fiscal_period", "gold_value",
          "gold_unit", "superseded_value", "nonexistent_segment",
          "source_form", "source_filed_date", "source_url", "what_to_check"]


def main() -> int:
    records = gold.read(DATA_DIR / "gold.jsonl")
    always = [r for r in records if r["category"] in ("false_premise", "covenant")]
    rest = [r for r in records if r["category"] not in ("false_premise", "covenant")]

    rng = random.Random(SEED)
    sample = rng.sample(rest, min(SAMPLE_OTHERS, len(rest)))
    selected = always + sample

    # The automated pre-check cannot prove a segment is absent from the filings,
    # only that it is absent from our corpus. Records where even that much could
    # not be established carry the real risk, so they sort to the top.
    precheck = {c.question_id: c for c in false_premise.check(records)}
    def priority(record):
        status = precheck.get(record["question_id"])
        if status and status.status != "absent_confirmed":
            return 0
        if record["category"] in ("covenant", "false_premise"):
            return 1
        return 2

    selected.sort(key=lambda r: (priority(r), r["category"], r["company"],
                                 r["question_id"]))

    out = DATA_DIR / "verification_sheet.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in selected:
            row = dict(record)
            # The verifier checks the question as the model will see it, not
            # the fields it was assembled from.
            row["question"] = prompts.question_text(
                record, prompts.ticker_for(record["cik"]))
            row["verified_ok"] = ""
            row["actual_value_if_wrong"] = ""
            row["notes"] = ""
            row["what_to_check"] = CHECK.get(record["category"], "")
            status = precheck.get(record["question_id"])
            row["precheck"] = status.status if status else ""
            row["priority"] = priority(record)
            row.setdefault("nonexistent_segment", "")
            writer.writerow(row)

    from collections import Counter
    counts = Counter(r["category"] for r in selected)
    print(f"{len(selected)} records to verify -> {out}")
    for category, n in sorted(counts.items()):
        total = sum(1 for r in records if r["category"] == category)
        print(f"  {category:<14} {n:>3} of {total}")
    urgent = sum(1 for r in selected if priority(r) == 0)
    confirmed = sum(1 for c in precheck.values() if c.status == "absent_confirmed")
    print(f"\nfalse-premise pre-check: {confirmed} of {len(precheck)} confirmed absent "
          f"automatically")
    print(f"{urgent} records sorted to the top as unconfirmed - check these first")
    print(f"\nseed={SEED} (fixed, so the draw cannot be quietly redrawn)")
    print("Fill verified_ok with y or n, then run scripts/apply_verification.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
