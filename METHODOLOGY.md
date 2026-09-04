# Methodology

## Scope

Closed-book is the primary track: no filing is provided, so the benchmark
measures parametric recall — how these tools are actually used by an analyst
typing into a chat box. An open-book track using deterministic excerpts runs
as a secondary comparison. The *contrast* between the tracks is the point;
neither number is very interesting alone.

This is deliberately not FinanceBench. That benchmark is open-book: the model
is handed the filing (or a retrieval system that fetches it), so it measures
whether a model can find and read the right number. Accuracy here is the
control variable. Calibration is the headline.

## Grading rules (frozen before any model was called)

Numeric answers are graded at the precision the model stated, with a 0.1%
relative floor, after unit normalisation. So "$96.8 billion" is correct
against a gold value of 96,773,000,000, but "about $100 billion" is not.

Rationale: strict exact-match on the filing's significant figures would mark
correctly-rounded answers wrong. That understates accuracy, which in turn
inflates the headline confident-wrong rate — the single number this project
exists to report. Getting it wrong in the direction that flatters the thesis
is exactly the error a reviewer looks for first.

Scale errors — answers off by a factor of 1000, 10^6 or 10^9 — are tracked as
a separate class and never counted correct. They are a different failure mode
from a wrong figure.

The rule lives in `config/grading.yaml`. The commit that introduced it
predates every file in `results/`; check `git log` to verify the ordering
rather than taking this paragraph's word for it.

## Confidence elicitation

Confidence is requested in the same response as the answer, in a fixed JSON
schema with an explicit abstain path. A separate call would let the model see
its own answer before rating it, which measures something different.

The schema is **prompt-instructed, not provider-enforced**. Enforcing it via
structured outputs would guarantee clean parsing, but it would also erase a
finding: whether a cheaper model can follow the confidence format at all is
part of what the tier comparison is measuring. Format-adherence rate is
reported per model, and a phrase-matching fallback parser (see
`config/grading.yaml`) catches schema violations so they score as data rather
than as errors.

## Scoping decisions

Financial-sector companies (Berkshire Hathaway, AIG, Capital One, Truist)
supply only share-count, cover-page, post-cutoff, restatement and
false-premise questions. No segment-revenue extraction: their taxonomy
concepts and segment disclosure do not map onto the same pipeline.

Carnival files as a dual-listed structure (Corporation & plc) and is excluded
from share-count questions.

Company selection is for structural messiness, not size. Salience is recorded
as a continuous variable (`dei:EntityPublicFloat`, free from the 10-K cover
page) and used at analysis time, not as a tier split or a filter.

## Segment data source

<!-- Filled in at Task 1.5 after the timeboxed spike. -->

## Segment data source

`companyfacts` returns non-dimensional facts only, so segment revenue needs a
separate source. The spec budgeted a day for parsing raw XBRL instance
documents. A timeboxed spike found a cheaper path and it was taken.

**Chosen: SEC Financial Statement *and Notes* Data Sets**, published monthly at
`https://www.sec.gov/files/dera/data/financial-statement-notes-data-sets/{YYYY_MM}_notes.zip`.
Segment facts come out of a table join rather than XML parsing:

    num.tsv (adsh, tag, ddate, qtrs, uom, dimh, value, coreg)
      -> dim.tsv (dimhash -> segments string)
      -> sub.tsv (adsh -> cik, form, filed)
      -> tag.tsv (tag -> tlabel, human-readable member names)

Two details cost time and are recorded so nobody repeats them. The datasets
switched from quarterly (`2025q2_notes.zip`) to monthly (`2026_07_notes.zip`)
filenames. And `dim.tsv` stores axis names with the `Statement` prefix and
`Axis` suffix stripped, so `us-gaap:StatementBusinessSegmentsAxis` appears as
`BusinessSegments`; searching for the full tag name returns nothing.

### The disaggregation rule

A fact is used only when nothing disaggregates it below the axis being asked
about. A row dimensioned on `BusinessSegments` *and* `ProductOrService` is a
product line inside a segment, not the segment: both would answer "what was the
X segment's revenue" differently, which is the genuine-ambiguity failure mode
the adversarial review exists to catch. Rows carrying a `coreg` value are
dropped too, since those report a co-registrant subsidiary's books.

Not every companion axis disaggregates, and an early version of this rule got
that wrong. `ConsolidationItems=OperatingSegments` is a *qualifier* meaning
"this row is the operating-segment total" - the single most common way segment
revenue is tagged. Rejecting it as ambiguous discarded most of the usable data:
on the 2026_07 file it cut 602 clean rows to 108, and across the corpus it cost
7,486 facts down to 2,624. Other members of that same axis
(`IntersegmentElimination`, `CorporateNonSegment`, `MaterialReconcilingItems`)
genuinely are reconciliation rows rather than segment revenue, so the allowance
is member-specific rather than axis-wide.

Final corpus: **7,486 segment and geographic facts** across 13 monthly notes
datasets (2025_07 through 2026_07; 2025_06 and 2026_08 are not published).

Geographic facts (`Geographical` axis) are kept alongside business segments and
supply the `deep` difficulty tier.

## Density screen outcome

All 58 candidates were scored against live EDGAR before any question was
written. **No company was swapped out.** The alternates list was not needed.

The screen asks one question per company - can it supply the share of
questions its role is assigned in the spec's section 6.4 supply table? - so
the thresholds are the quotas themselves (C: 4, F: 2, G: 1 buried questions;
A and D: 3 restatements) rather than numbers chosen to produce a comfortable
answer.

Richness is measured in usable segment-revenue **facts**, not distinct segment
members. Amazon reports three segments and reports them every quarter;
counting members alone would call it thin when it can in fact supply many
questions.

Confirmed:

| Role | Companies | Result |
|---|---|---|
| A - recast-heavy parents | 16 | all keep; 60-438 usable restatements each |
| B - short-history spin-offs | 5 | all keep; correctly thin by construction (GEV 0, VLTO 0, SOLV 1 restatements) |
| C - multi-segment reporters | 11 | all keep |
| D - financials | 4 | all keep |
| E - share-structure complexity | 4 | all keep |
| F - fiscal-calendar traps | 5 | all keep |
| G - leverage / covenant | 5 | 3 keep, 2 flagged (see below) |

Segment coverage: 5,931 usable revenue facts across 55 of 58 companies (4,330
on the business-segment axis, 1,601 geographic, 1,504 of them annual). Against
a buried-but-knowable quota of 99, the surplus is large.

### The two flagged companies

Charter (CHTR) and Community Health (CYH) return zero segment facts. This is a
fact about them, not a pipeline failure: both operate as effectively
single-segment businesses. They are **kept**, because their assigned role is
covenant and restatement questions (CHTR has 40 usable restatements, CYH 53),
and the screen does not measure covenant supply at all. The two
buried-but-knowable questions they would have contributed are drawn from the
surplus elsewhere.

Truist (TFC) also returns zero segment facts, which is expected and not a
defect: the financials scoping decision above bars segment-revenue extraction
for role D entirely. Role D's buried-question quota is met with share-count and
cover-page questions sourced from `companyfacts`.

## Density screen results

All 58 candidates (50 primaries + 8 alternates) were scored against live EDGAR.
**No company failed the screen**, so the universe is the 50 as specified and the
8 alternates remain an unused bench.

The role hypotheses in the spec held up:

- **Role A (recast-heavy parents), 16/16 keep.** 60-438 usable restatements
  each. The restatement engine works as designed.
- **Role B (short-history spin-offs), 5/5 keep.** Correctly thin by
  construction - GE Vernova and Veralto have zero restatements, Solventum one.
  That is what they are in the universe to provide.
- **Roles C and F** are judged on segment supply, **roles A, D and G** on
  restatement supply, and **roles B and E** are always kept. The verdict is
  role-aware because one global threshold keeps the wrong companies: a
  recast-heavy parent with rich segments but no restatements is useless to the
  restatement track, and vice versa.

### Why role G is not judged on segments

Role G (leverage/covenant) was initially scored on segment richness, which
flagged Charter and Community Health as thin. That was the screen testing
something the role was never there to supply: role G's questions come from
covenant prose and Exhibit 10 credit agreements, sourced manually, which this
screen cannot measure at all. Charter and Community Health report as
near-single-segment, which is a true fact about those companies rather than a
data gap. Role G is therefore judged on restatement supply, where both clear
the threshold comfortably (Charter 40, Community Health 53).

## Model roster

Pinned on 2026-09-02 from OpenRouter's live catalogue (426 models), never from
memory. See `config/models.yaml`; re-run `scripts/preflight_models.py` before
any run.

| Slot | Role | Model | $/Mtok in/out |
|---|---|---|---|
| 1 | Flagship | `openai/gpt-5.6-sol` | 2.00 / 10.00 |
| 2 | Flagship | `anthropic/claude-opus-5` | 5.00 / 25.00 |
| 3 | Flagship | `google/gemini-3.1-pro-preview` | 2.00 / 12.00 |
| 4 | Flagship | `x-ai/grok-4.6` | 2.00 / 6.00 |
| 5 | Cheap tier | `openai/gpt-5.6-luna` | 0.20 / 1.20 |
| ref | Retrieval | `perplexity/sonar-pro` | 3.00 / 15.00 |

Slot 5 pairs against slot 1 within the **same generation** (5.6), at 10x lower
input cost. A cheap model paired against a flagship of a different vintage
would confound model size with model age and make the tier comparison
unreadable.

The reasoning-toggle subset runs on `claude-opus-5` - deliberately a different
family from the tier pair, so the two experiments cannot confound each other.

Google's slot is a `-preview` endpoint, which the lab can update silently. The
mitigation is the harness recording the resolved model string on every row and
quarantining any call whose resolved model differs from the requested one.

## Verification

<!-- Filled in at Task 1.9 and Milestone 4: human-verified count, and the
     abstention classification agreement rate on a random 100. -->
