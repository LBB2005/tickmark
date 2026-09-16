# Gold verification report

Human decision still required: this file and `data/verification_proposed.csv` are evidence, not an applied verification pass. `data/gold.jsonl` was not edited.

Filings were opened through `finbench.http.SecClient` (User-Agent, throttle, on-disk cache). Values were checked in the primary 10-K/10-Q HTML, then cross-checked against `companyfacts` start/end for duration.

## 1. Summary counts

78 sample rows (`data/verification_sheet.csv`). Proposed verdicts:

| category | y | n | unsure | total |
|---|---:|---:|---:|---:|
| false_premise | 38 | 0 | 0 | 38 |
| buried | 8 | 1 | 0 | 9 |
| post_cutoff | 9 | 0 | 0 | 9 |
| post_cutoff_boundary | 13 | 2 | 0 | 15 |
| restatement | 6 | 1 | 0 | 7 |
| **all** | **74** | **4** | **0** | **78** |

Priority-0 false-premise rows (Salesforce, WK Kellogg ×3): all **y**. Latest 10-Ks confirm the named segments do not exist.

## 2. Every n row

No `unsure` rows. The four `n` rows:

### pcb-DD-2024-03-31 (post_cutoff_boundary)

- Gold: "fiscal year ended March 31, 2024", $1,599,000,000, source FY2025 10-K filed 2026-02-17.
- Found: **three months** ended March 31, 2024 (recast continuing-operations net sales).
- Evidence, FY2025 10-K selected quarterly data: `Year ending December 31, 2024: Net sales $ 1,599 $ 1,717 $ 1,714 $ 1,689` ([dd-20251231.htm](https://www.sec.gov/Archives/edgar/data/1666700/000166670026000013/dd-20251231.htm)).
- companyfacts: `start=2024-01-01`, `end=2024-03-31`, form 10-K, accession `0001666700-26-000013`.
- DuPont's fiscal year ends in December. Annual revenue is ~$10–12B, not $1.6B.
- **Suspected cause:** `build_cutoff_boundary` labels the period with `periods.phrase_for_form(form, obs.end)` using the *filing* form. A Q1 comparative whose latest accession is a 10-K becomes "fiscal year".

### pcb-HON-2024-03-31 (post_cutoff_boundary)

- Gold: "fiscal year ended March 31, 2024", $8,157,000,000, source FY2025 10-K filed 2026-02-17.
- Found: **three months** ended March 31, 2024.
- Evidence: `2024 March 31 June 30 September 30 December 31 Net sales $ 8,157 $ 8,572 $ 8,819 $ 9,169` ([hon-20251231.htm](https://www.sec.gov/Archives/edgar/data/773840/000077384026000013/hon-20251231.htm)).
- companyfacts: `start=2024-01-01`, `end=2024-03-31`. Honeywell FYE is December; sibling record `pcb-HON-2025-03-31` is correctly labeled as a quarter ($8,925M).
- **Suspected cause:** same `phrase_for_form(10-K, …)` bug as DuPont.

### bur-m-COST-UnitedStates-2026-04-30-1 (buried)

- Gold: United States revenue, "three months ended April 30, 2026", $51,434,000,000.
- Found: **12 weeks ended May 10, 2026**, United States total revenue $51,434 million ([cost-20260510.htm](https://www.sec.gov/Archives/edgar/data/909832/000090983226000051/cost-20260510.htm)). Filing `reportDate=2026-05-10`.
- Costco does not have a period ending April 30, 2026.
- **Suspected cause:** segment facts take `num.tsv` `ddate` (2026-04-30, calendar month-end) as `fiscal_period_end` instead of the 10-Q's report date.

### rst-AMZN-01 (restatement)

- Gold: "fiscal year ended September 30, 2016", financing cash −$4,746,000,000; superseded −$4,345,000,000.
- Both numbers appear, for the **same** 12-month span:
  - Later Q3 2017 10-Q: financing cash `(4,746)` ([amzn-20170930x10q.htm](https://www.sec.gov/Archives/edgar/data/1018724/000101872417000135/amzn-20170930x10q.htm)).
  - Earlier Q3 2016 10-Q: `(4,345)` ([amzn-20160930x10q.htm](https://www.sec.gov/Archives/edgar/data/1018724/000101872416000324/amzn-20160930x10q.htm)).
- companyfacts period is `2015-10-01` … `2016-09-30` (TTM). Amazon's fiscal year ends December 31.
- **Suspected cause:** `periods.phrase` calls any span with `qtrs >= 4` "the fiscal year", including a trailing-twelve-months tag in a 10-Q.

## 3. Systematic issues

### 3.1 `phrase_for_form` on cutoff-boundary observations (main bug)

**Root cause.** `build_cutoff_boundary` already has the observation's `start` and `end`. It then throws that duration away and phrases from the *source filing's form*:

```275:275:scripts/build_gold.py
                fiscal_period=periods.phrase_for_form(form, obs.end),
```

```40:49:src/finbench/periods.py
def phrase_for_form(form: str, end: str) -> str:
    ...
    if form.startswith("10-K"):
        return phrase(None, end, qtrs=4)
    return phrase(None, end, qtrs=1)
```

`form` comes from the submissions row for `obs.accn`. Two failures follow:

1. A 3-month comparative whose latest accession is a 10-K is labeled a fiscal year (DuPont, Fortive, Honeywell).
2. A 6- or 9-month YTD fact in a 10-Q is labeled "three months" (Nike, Oracle, Costco 2024, Disney 2024, …).

Restatements and buried records already call `periods.phrase(start, end)` / `phrase(..., qtrs=)`. `phrase_for_form` is the right helper for `build_post_cutoff` (ask about the filing's own report period, value is null) and is the wrong helper once a specific observation has been chosen.

**Affected gold records: 13 of 98 `post_cutoff_boundary` (0 of the other 260).** Value-matched in companyfacts:

| question_id | labeled | actual duration | in the 78-row sample? |
|---|---|---|---|
| pcb-DD-2024-03-31 | fiscal year | 3 months | yes |
| pcb-FTV-2024-03-29 | fiscal year | 3 months | no |
| pcb-HON-2024-03-31 | fiscal year | 3 months | yes |
| pcb-BDX-2024-03-31 | three months | 6 months | no |
| pcb-COST-2024-02-18 | three months | 6 months (24 weeks) | no |
| pcb-DIS-2024-03-30 | three months | 6 months | no |
| pcb-EMR-2024-03-31 | three months | 6 months | no |
| pcb-FOXA-2024-03-31 | three months | 9 months | no |
| pcb-NKE-2024-02-29 | three months | 9 months | no |
| pcb-NWSA-2024-03-31 | three months | 9 months | no |
| pcb-ORCL-2024-02-29 | three months | 9 months | no |
| pcb-WDC-2024-03-29 | three months | 9 months | no |
| pcb-WDC-2025-03-28 | three months | 9 months | no |

11 of 13 sit outside the random sample. The sample drew the 2025 Costco/Disney/News Corp quarters (correct 3-month facts) and missed the 2024 YTD twins. That is why this class would have survived a sample-only review.

Legitimate 10-K / "fiscal year" boundary records, left alone: `pcb-CRM-2024-01-31`, `pcb-CRM-2025-01-31` (Salesforce FYE Jan 31), `pcb-MCK-2024-03-31`, `pcb-MCK-2025-03-31` (McKesson FYE March 31), `pcb-K-2024-12-28` (Kellanova late-December year).

**Proposed code fix (do not apply to gold here).** In `build_cutoff_boundary`, phrase from the observation:

```python
fiscal_period=periods.phrase(obs.start, obs.end),
```

Optional tightening: drop candidates whose duration is 2 or 3 quarters if the product intent is "quarter or year only". Labeling YTD correctly is enough to stop silent wrong answers.

**Failing tests:** `tests/test_cutoff_boundary_periods.py` (quarter-in-10-K and 9-month-in-10-Q). They fail on current `main` and will pass once the line above is changed. Gold is not rebuilt.

### 3.2 `periods.phrase` calls every 12-month span a fiscal year

**Root cause.** `src/finbench/periods.py:29-30`: `if qtrs >= 4: return f"the fiscal year ended {_pretty(end)}"`.

**Affected gold records: 1** — `rst-AMZN-01` (TTM ended 2016-09-30, sourced from a 10-Q). No other restatement in the 77 uses a 12-month span that does not end on that company's actual FYE (McKesson March 31 is a real FYE).

**Proposed fix.** If the end date is more than ~15 days from the company's fiscal year-end, say "the twelve months ended {date}" rather than "the fiscal year". That needs a FYE on each company. `config/companies.yaml` currently has no `fiscal_year_end` field, so the check cannot be written without adding one (or inferring FYE from each company's 10-K `reportDate`s).

### 3.3 Notes `ddate` vs filing `reportDate` on 52-week filers

**Root cause.** `src/finbench/dimensional.py:240` sets `end = _ddate_to_iso(row["ddate"])`. SEC notes `ddate` is often the calendar month-end, not the Saturday/Friday on the 10-Q cover. `_start_for` then back-computes start from that wrong end.

**Affected gold records: 24 buried** (none of the other categories, which do not use notes `ddate`):

`bur-m-INTC-ClientComputingAndPhysicalAIGroup-2026-06-30-1`, `bur-m-INTC-DatacenterAndAI-2026-06-30-1`, `bur-d-INTC-US-2025-12-31-4`, `bur-m-K-EuropeSegment-2025-09-30-1`, `bur-m-K-NorthAmericaSegment-2025-09-30-1`, `bur-m-WDC-HDD-2026-03-31-1`, `bur-m-WDC-HDD-2026-03-31-3`, `bur-d-WDC-Asia-2026-03-31-1`, `bur-m-JNJ-InnovativeMedicine-2026-06-30-1`, `bur-d-JNJ-US-2026-06-30-1`, `bur-m-TXT-Bell-2026-06-30-1`, `bur-d-TXT-US-2026-06-30-1`, `bur-m-DHR-LifeSciencesSegment-2026-06-30-1`, `bur-d-DHR-OtherDevelopedMarkets-2026-06-30-1`, `bur-m-DE-ConstructionAndForestrySegment-2026-04-30-1`, `bur-d-DE-AsiaAfricaOceaniaAndMiddleEast-2026-04-30-1`, `bur-m-COST-UnitedStates-2026-04-30-1`, `bur-m-FTV-AdvancedHealthcareSolutions-2026-06-30-1`, `bur-d-FTV-NorthAmerica-2026-06-30-1`, `bur-m-AVGO-SemiconductorSolutions-2026-04-30-1`, `bur-d-AVGO-Americas-2026-04-30-1`, `bur-m-DIS-SegmentEliminations-2026-03-31-1`, `bur-m-KVUE-SkinHealthAndBeauty-2026-03-31-1`, `bur-m-VLTO-WaterQualitySegment-2026-06-30-1`.

Most are a 1–4 day Saturday year-end drift (Intel June 27 vs June 30). Costco is the one that is actually wrong: April 30 vs May 10. Deere/Broadcom are ~3 days (April 30 vs May 3).

**Proposed fix.** Prefer `sub.tsv` `period` for that `adsh` when it disagrees with `ddate` by less than a month; phrase from that date. For Costco-class 52/53-week retailers, never emit a calendar month-end the company does not use.

## 4. Pipeline risks the 78-row sample would miss

1. **YTD-as-quarter boundary records (11 of the 13 in §3.1).** The sample's Costco/Disney/News Corp rows are the *correct* 2025 quarters. The broken 2024 YTD twins (`pcb-COST-2024-02-18` $116B labeled as three months, `pcb-DIS-2024-03-30` $45.6B, `pcb-NKE-2024-02-29` $38.8B, `pcb-ORCL-2024-02-29` $38.7B, plus BDX/EMR/FOXA/NWSA/WDC) are not in the sheet.

2. **`bur-m-DIS-SegmentEliminations-2026-03-31-1` (−$643M) and `bur-m-PSX-ChemicalsSegment-2026-03-31-1` ($0).** `is_generic_member` rejects a label equal to `"eliminations"` but not `"segment eliminations"`, so a reconciling line became a buried question. A $0 chemicals fact is a legal XBRL row and a bad question. Neither is in the sample.

3. **`companies.yaml` has no fiscal year-end.** Role F exists specifically for fiscal-calendar traps, but nothing in gold assembly can assert "this end date is (or is not) this company's FYE". That is why DuPont-March and Amazon-September were emit-able.

4. **False-premise period labels on 10-Q companies** use `phrase_for_form` on the latest filing. That is fine (they ask about the quarter the latest 10-Q covers). Do not "fix" those with the boundary change.

5. **Restatement gold_obs can be an 8-K.** Danaher's later $769.4M also appears on an 8-K filed after the 10-K we point at. The 10-K still has the number; no sample failure. A later rebuild that keyed on the latest accession regardless of form could point humans at an 8-K.

6. **WK Kellogg / Salesforce had no segment facts** (`precheck=no_segment_data`). The latest 10-Ks confirm the premises are false. Keep the human pass on `no_segment_data` rows; the automated corpus check cannot see a single-segment 10-K.

## 5. Sample rows that are proposed y (short)

- **38 false_premise:** latest 10-K segment note does not name the borrowed segment. Priority 0: Salesforce is one operating segment; WK Kellogg is one North America cereal segment (AMEA / Europe / Latin America are Kellanova).
- **8 other buried:** Japan FY2025 $30,688M; Carnival US Q2 $3,593M; Emerson S&P $547M; GE D&P $3,443M; Kellanova NA $1,627M (quarter ended Sept 27); Textron 171,986,917 shares as of July 17, 2026; Truist 1,221,626,188 as of June 30, 2026; WBD Studios Q1 2026 $3,125M.
- **9 post_cutoff:** each 10-Q covers the named quarter and was filed on `source_filed_date`.
- **13 other pcb:** gold figure appears as the 3-month (or Costco 12-week) number for that end date. Several 10-Qs also show a 6/9-month column with a *different* number; gold matched the quarter column.
- **6 other restatements:** both the superseded and gold figures appear for the same annual period in the earlier and later 10-Ks (Danaher 2014 R&D, DuPont 2020 tax, Honeywell 2008 tax, J&J FY2021 COGS, Salesforce FY2018 EPS, WDC FY2024 tax).

## 6. Tests

`tests/test_cutoff_boundary_periods.py` is the failing contract for §3.1. Run: `.venv/bin/python -m pytest -q`.
