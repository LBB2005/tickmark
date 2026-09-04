"""Locate covenant language for the leverage/covenant companies (spec 5.2).

The spec is explicit that this bucket is manual and capped at 15-20 questions,
and that EDGAR full-text search is the way in rather than reading filings front
to back. This script does the locating; a human reads the hit and writes the
gold record.

It deliberately stops at candidates. Extracting a covenant threshold from prose
is exactly the kind of judgement that should not be automated into a benchmark's
ground truth.
"""
from __future__ import annotations

import csv
import sys
from urllib.parse import quote

from finbench import config
from finbench.http import SecClient

FTS = "https://efts.sec.gov/LATEST/search-index?q=%22{phrase}%22&forms={forms}&ciks={cik}"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{doc}"

PHRASES = [
    "consolidated leverage ratio",
    "consolidated net leverage ratio",
    "total net leverage ratio",
    "maximum leverage ratio",
    "interest coverage ratio",
    "fixed charge coverage ratio",
    "minimum liquidity",
    "restricted payments",
]
FORMS = "10-K,10-Q"
COVENANT_ROLES = ("G",)


def main() -> int:
    config.load_dotenv()
    companies = [c for c in config.companies()["companies"]
                 if c["role"] in COVENANT_ROLES]
    print(f"searching {len(companies)} covenant-role companies "
          f"x {len(PHRASES)} phrases\n")

    rows = []
    with SecClient(min_interval=0.4) as client:
        for company in companies:
            for phrase in PHRASES:
                url = FTS.format(phrase=quote(phrase), forms=FORMS,
                                 cik=f"{company['cik']:010d}")
                try:
                    payload = client.get_json(url)
                except Exception as exc:  # noqa: BLE001
                    print(f"  {company['ticker']:<6} {phrase[:28]:<28} ERROR {type(exc).__name__}")
                    continue
                hits = (payload.get("hits") or {}).get("hits") or []
                total = ((payload.get("hits") or {}).get("total") or {}).get("value", 0)
                print(f"  {company['ticker']:<6} {phrase[:30]:<30} {total:>4} hits")
                for hit in hits[:3]:
                    source = hit.get("_source") or {}
                    accn, _, doc = hit.get("_id", "").partition(":")
                    if not accn:
                        continue
                    rows.append({
                        "ticker": company["ticker"],
                        "company": company["name"],
                        "cik": company["cik"],
                        "phrase": phrase,
                        "form": (source.get("file_type") or source.get("root_form") or ""),
                        "filed": source.get("file_date", ""),
                        "period": source.get("period_ending", ""),
                        "accession": accn,
                        "url": ARCHIVE.format(cik=company["cik"],
                                              accn=accn.replace("-", ""), doc=doc),
                    })

    out = config.DATA_DIR / "covenant_candidates.csv"
    if not rows:
        print("\nno candidates found", file=sys.stderr)
        return 1
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)} candidate documents -> {out}")
    print("Read these and hand-write gold records into data/gold_covenant.jsonl")
    print("(answer_type=text, category=covenant, verification=human)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
