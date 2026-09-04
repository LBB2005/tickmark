"""Assemble gold records from every source (spec section 5.4 / 6.4).

Every record is derived from a fact already held. Nothing here writes a
question; questions come later, from templates, in Milestone 2.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
from collections import defaultdict
from typing import Any

from finbench import (config, dimensional, edgar, gold, observations,
                      periods, restatements)
from finbench.http import SecClient

SHARE_CONCEPT = "EntityCommonStockSharesOutstanding"
HEADLINE_CONCEPTS = {
    "Revenues": "revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "NetIncomeLoss": "net income",
    "OperatingIncomeLoss": "operating income",
}
# Spec section 4: financials source no segment-revenue questions, and Carnival
# is excluded from share-count questions (dual-listed Corporation & plc).
NO_SEGMENT_ROLES = {"D"}
NO_SHARE_COUNT_TICKERS = {"CCL"}

RESTATEMENTS_PER_ROLE = {"A": 3, "C": 2, "D": 2}
# A "post-cutoff" period has to actually be recent. WK Kellogg stopped filing
# after its 2025 acquisition, so its newest period is over a year old and
# would be squarely inside every model's training data.
POST_CUTOFF_MAX_AGE_DAYS = 300
BURIED_TARGET = {"headline": 20, "mid": 50, "deep": 30}

# Spec 7.4 requires scoring the post-cutoff bucket against EACH model's own
# boundary. That machinery only does anything if some questions land on
# different sides for different models. Taking only each company's newest
# filing put all 48 records 8-25 months past every model's stated cutoff, with
# 37 of 48 in a single month - valid, but every one of them "obviously recent",
# which is precisely the case spec 7.4 predicts models handle correctly.
#
# These boundary records span the window that the measured stated cutoffs
# actually fall in (2024-06 for gpt-5.6, 2025-01 for opus-5 and gemini-3.1,
# 2024-10 for grok-4.6), so a given record is post-cutoff for some models and
# answerable for others. They carry the TRUE value; the harness decides per
# model which behaviour is correct.
BOUNDARY_WINDOW = ("2024-01-01", "2026-03-31")
BOUNDARY_PER_COMPANY = 2


def source_url(cik: int, accession: str) -> str:
    return (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
            f"{accession.replace('-', '')}/{accession}-index.htm")


def kept_universe() -> list[dict[str, Any]]:
    rows = list(csv.DictReader((config.DATA_DIR / "screen.csv").open()))
    return [r for r in rows if r["verdict"] == "KEEP" and r["role"] != "ALT"]


def base_record(**kw: Any) -> dict[str, Any]:
    record = {
        "question_id": kw["question_id"], "company": kw["company"], "cik": kw["cik"],
        "fiscal_period": kw["fiscal_period"], "fiscal_period_end": kw["fiscal_period_end"],
        "concept": kw["concept"], "answer_type": kw["answer_type"],
        "gold_value": kw.get("gold_value"), "gold_unit": kw.get("gold_unit"),
        "superseded_value": kw.get("superseded_value"),
        "source_accession": kw["source_accession"], "source_form": kw["source_form"],
        "source_filed_date": kw["source_filed_date"], "source_url": kw["source_url"],
        "category": kw["category"], "difficulty": kw.get("difficulty"),
        "verification": "auto", "verified_by": None, "verified_date": None,
    }
    for extra in ("segment_label", "segment_axis", "post_cutoff_actual",
                  "nonexistent_segment", "borrowed_from"):
        if extra in kw:
            record[extra] = kw[extra]
    return record


def build_restatements(universe, facts_by_cik) -> list[dict]:
    out = []
    for entry in universe:
        quota = RESTATEMENTS_PER_ROLE.get(entry["role"])
        if not quota:
            continue
        cik = int(entry["cik"])
        found = restatements.find(facts_by_cik[cik])
        # Prefer annual periods: a recast fiscal year is the cleanest question.
        found.sort(key=lambda r: (not periods.is_annual(r.start, r.end),
                                  -r.relative_change))
        for i, r in enumerate(found[:quota]):
            out.append(base_record(
                question_id=f"rst-{entry['ticker']}-{i:02d}",
                company=entry["name"], cik=cik,
                fiscal_period=periods.phrase(r.start, r.end),
                fiscal_period_end=r.end, concept=r.concept,
                answer_type="numeric", gold_value=r.gold_value, gold_unit=r.unit,
                superseded_value=r.superseded_value,
                source_accession=r.source_accn, source_form=r.source_form,
                source_filed_date=r.source_filed,
                source_url=source_url(cik, r.source_accn),
                category="restatement", difficulty=None))
    return out


def build_buried(universe, facts_by_cik, segments_by_cik) -> list[dict]:
    out: list[dict] = []
    by_ticker = {int(e["cik"]): e for e in universe}

    # headline - consolidated figures and cover-page share counts
    headline: list[dict] = []
    for entry in universe:
        cik = int(entry["cik"])
        facts = facts_by_cik[cik]
        annual = [o for o in observations.iter_observations(facts)
                  if o.concept in HEADLINE_CONCEPTS and o.form == "10-K"
                  and periods.is_annual(o.start, o.end)]
        annual.sort(key=lambda o: (o.filed, o.end), reverse=True)
        if annual:
            o = annual[0]
            headline.append(base_record(
                question_id=f"bur-h-{entry['ticker']}",
                company=entry["name"], cik=cik,
                fiscal_period=periods.phrase(o.start, o.end),
                fiscal_period_end=o.end, concept=o.concept,
                answer_type="numeric", gold_value=o.val, gold_unit=o.unit,
                source_accession=o.accn, source_form=o.form,
                source_filed_date=o.filed, source_url=source_url(cik, o.accn),
                category="buried", difficulty="headline"))
        if entry["ticker"] in NO_SHARE_COUNT_TICKERS:
            continue
        shares = [o for o in observations.iter_observations(facts, taxonomy="dei")
                  if o.concept == SHARE_CONCEPT]
        shares.sort(key=lambda o: (o.filed, o.end), reverse=True)
        if shares:
            o = shares[0]
            headline.append(base_record(
                question_id=f"bur-s-{entry['ticker']}",
                company=entry["name"], cik=cik,
                fiscal_period=periods.phrase(None, o.end),
                fiscal_period_end=o.end, concept=o.concept,
                answer_type="numeric", gold_value=o.val, gold_unit=o.unit,
                source_accession=o.accn, source_form=o.form,
                source_filed_date=o.filed, source_url=source_url(cik, o.accn),
                category="buried", difficulty="headline"))

    # mid  = business-segment revenue; deep = geographic revenue
    tiers: dict[str, list[dict]] = {"mid": [], "deep": []}
    for cik, facts in segments_by_cik.items():
        entry = by_ticker.get(cik)
        if entry is None or entry["role"] in NO_SEGMENT_ROLES:
            continue
        for fact in facts:
            if fact.concept not in dimensional.REVENUE_TAGS:
                continue
            tier = "mid" if fact.axis == dimensional.SEGMENT_AXIS else "deep"
            tiers[tier].append(base_record(
                question_id=(f"bur-{tier[0]}-{entry['ticker']}-{fact.member}-"
                             f"{fact.end}-{fact.qtrs}"),
                company=entry["name"], cik=cik,
                fiscal_period=periods.phrase(fact.start, fact.end, fact.qtrs),
                fiscal_period_end=fact.end, concept=fact.concept,
                answer_type="numeric", gold_value=fact.val, gold_unit=fact.unit,
                source_accession=fact.accn, source_form=fact.form,
                source_filed_date=fact.filed, source_url=source_url(cik, fact.accn),
                category="buried", difficulty=tier,
                segment_label=fact.member_label, segment_axis=fact.axis))

    out.extend(_spread(headline, BURIED_TARGET["headline"]))
    for tier in ("mid", "deep"):
        out.extend(_spread(tiers[tier], BURIED_TARGET[tier]))
    return out


def _spread(records: list[dict], target: int) -> list[dict]:
    """Take `target` records, round-robin by company so no name dominates.

    Without this, JNJ's 600-row segment disclosure would supply most of the
    tier and the salience regression would be measuring one company.
    """
    if len(records) <= target:
        return records
    grouped: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["cik"]].append(record)
    for group in grouped.values():
        group.sort(key=lambda r: r["fiscal_period_end"], reverse=True)
    out: list[dict] = []
    index = 0
    while len(out) < target:
        added = False
        for cik in sorted(grouped):
            if index < len(grouped[cik]):
                out.append(grouped[cik][index])
                added = True
                if len(out) >= target:
                    break
        if not added:
            break
        index += 1
    return out


def build_post_cutoff(universe, submissions) -> list[dict]:
    out = []
    for entry in universe:
        cik = int(entry["cik"])
        recent = submissions.get(cik)
        if not recent:
            continue
        # Most recent periodic filing: its period is the newest thing on file
        # and therefore the most likely to postdate a model's training cutoff.
        form, report_date, filing_date, accession = recent[0]
        age = (dt.date.today() - dt.date.fromisoformat(report_date)).days
        if age > POST_CUTOFF_MAX_AGE_DAYS:
            print(f"  post-cutoff SKIP {entry['ticker']}: newest period "
                  f"{report_date} is {age} days old")
            continue
        out.append(base_record(
            question_id=f"pc-{entry['ticker']}",
            company=entry["name"], cik=cik,
            fiscal_period=periods.phrase_for_form(form, report_date),
            fiscal_period_end=report_date, concept="Revenues",
            answer_type="post_cutoff", gold_value=None, gold_unit="USD",
            source_accession=accession, source_form=form,
            source_filed_date=filing_date, source_url=source_url(cik, accession),
            category="post_cutoff", difficulty=None))
    return out


def build_cutoff_boundary(universe, facts_by_cik, submissions) -> list[dict]:
    """Post-cutoff records that straddle the models' stated cutoffs."""
    low, high = BOUNDARY_WINDOW
    out = []
    for entry in universe:
        cik = int(entry["cik"])
        facts = facts_by_cik.get(cik)
        rows = submissions.get(cik)
        if not facts or not rows:
            continue
        by_accession = {r[3]: r for r in rows}

        # Latest-filed value per period, so the figure is the current one.
        candidates: dict[tuple, Any] = {}
        for obs in observations.iter_observations(facts):
            if obs.concept not in ("Revenues",
                                   "RevenueFromContractWithCustomerExcludingAssessedTax"):
                continue
            if obs.form not in ("10-K", "10-Q") or obs.unit != "USD":
                continue
            if obs.start is None or not (low <= obs.end <= high):
                continue
            if obs.accn not in by_accession:
                continue
            key = (obs.start, obs.end)
            if key not in candidates or obs.filed > candidates[key].filed:
                candidates[key] = obs
        if not candidates:
            continue

        # Spread the picks across the window rather than clustering.
        chosen = sorted(candidates.values(), key=lambda o: o.end)
        step = max(1, len(chosen) // BOUNDARY_PER_COMPANY)
        picks = chosen[::step][:BOUNDARY_PER_COMPANY]
        for obs in picks:
            form, report_date, filing_date, accession = by_accession[obs.accn]
            out.append(base_record(
                question_id=f"pcb-{entry['ticker']}-{obs.end}",
                company=entry["name"], cik=cik,
                fiscal_period=periods.phrase_for_form(form, obs.end),
                fiscal_period_end=obs.end, concept=obs.concept,
                answer_type="numeric", gold_value=obs.val, gold_unit="USD",
                source_accession=obs.accn, source_form=obs.form,
                source_filed_date=obs.filed, source_url=source_url(cik, obs.accn),
                category="post_cutoff_boundary", difficulty=None))
    return out


def build_false_premise(universe, segments_by_cik, sic_by_cik, limit: int) -> list[dict]:
    """Borrow a real segment name from a peer in the same SIC major group.

    Plausible by construction, and verifiably absent from the target's own
    disclosure, so any number returned is fabrication.
    """
    own_members: dict[int, set[str]] = {}
    labels_by_sector: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for cik, facts in segments_by_cik.items():
        members = {f.member_label for f in facts
                   if f.axis == dimensional.SEGMENT_AXIS}
        own_members[cik] = members
        sector = sic_by_cik.get(cik, "")[:2]
        for label in members:
            labels_by_sector[sector].append((cik, label))

    out: list[dict] = []
    for entry in sorted(universe, key=lambda e: e["role"] != "B"):  # B first
        if len(out) >= limit:
            break
        cik = int(entry["cik"])
        sector = sic_by_cik.get(cik, "")[:2]
        mine = own_members.get(cik, set())
        candidates = [(o, lab) for o, lab in labels_by_sector.get(sector, [])
                      if o != cik and lab not in mine]
        if not candidates:  # fall back to any peer, still verifiably absent
            candidates = [(o, lab) for s, pairs in labels_by_sector.items()
                          for o, lab in pairs if o != cik and lab not in mine
                          and s != sector]
        seen: set[str] = set()
        take = 3 if entry["role"] == "B" else 1
        for other_cik, label in candidates:
            if len(out) >= limit or take == 0:
                break
            if label in seen:
                continue
            seen.add(label)
            take -= 1
            out.append(base_record(
                question_id=f"fp-{entry['ticker']}-{label.replace(' ', '')[:20]}",
                company=entry["name"], cik=cik,
                fiscal_period=periods.phrase_for_form(
                    entry.get("fp_form", "10-Q"), entry["fp_end"]),
                fiscal_period_end=entry["fp_end"],
                concept="Revenues", answer_type="none_exists",
                gold_value=None, gold_unit="USD",
                source_accession="", source_form="", source_filed_date="",
                source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
                category="false_premise", difficulty=None,
                nonexistent_segment=label, borrowed_from=other_cik))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--false-premise", type=int, default=38)
    args = ap.parse_args()

    config.load_dotenv()
    universe = kept_universe()
    print(f"universe: {len(universe)} companies (KEEP, excluding alternates)")

    facts_by_cik: dict[int, dict] = {}
    submissions: dict[int, list] = {}
    sic_by_cik: dict[int, str] = {}
    with SecClient() as client:
        for entry in universe:
            cik = int(entry["cik"])
            facts_by_cik[cik] = edgar.fetch_companyfacts(client, cik)
            sub = edgar.fetch_submissions(client, cik)
            sic_by_cik[cik] = str(sub.get("sic") or "")
            recent = sub["filings"]["recent"]
            rows = [(recent["form"][i], recent["reportDate"][i],
                     recent["filingDate"][i], recent["accessionNumber"][i])
                    for i in range(len(recent["form"]))
                    if recent["form"][i] in ("10-K", "10-Q") and recent["reportDate"][i]]
            rows.sort(key=lambda r: r[1], reverse=True)
            submissions[cik] = rows
            entry["fp_end"] = rows[0][1] if rows else "2025-12-31"
            entry["fp_form"] = rows[0][0] if rows else "10-K"

    segments_by_cik: dict[int, list] = defaultdict(list)
    for fact in dimensional.load_cached():
        segments_by_cik[fact.cik].append(fact)

    records: list[dict] = []
    records += build_restatements(universe, facts_by_cik)
    records += build_buried(universe, facts_by_cik, segments_by_cik)
    records += build_post_cutoff(universe, submissions)
    records += build_cutoff_boundary(universe, facts_by_cik, submissions)
    records += build_false_premise(universe, segments_by_cik, sic_by_cik,
                                   args.false_premise)

    # Deduplicate defensively; question_id collisions are a hard error later.
    unique: dict[str, dict] = {}
    for record in records:
        unique.setdefault(record["question_id"], record)
    records = list(unique.values())

    from collections import Counter
    print("\ncategory     count")
    for category, n in Counter(r["category"] for r in records).most_common():
        print(f"  {category:<13} {n}")
    print("\ndifficulty   count")
    for difficulty, n in Counter(r["difficulty"] for r in records).most_common():
        print(f"  {str(difficulty):<13} {n}")
    print("\nanswer_type  count")
    for answer_type, n in Counter(r["answer_type"] for r in records).most_common():
        print(f"  {answer_type:<13} {n}")

    path = config.DATA_DIR / "gold.jsonl"
    print(f"\n{gold.write(records, path)} records -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
