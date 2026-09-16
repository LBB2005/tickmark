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

## Segment qualifiers and conflicting values

`ConsolidationItems` carries more than one benign member. Alongside
`OperatingSegments`, GE Vernova tags Electrification, Power and Wind
*exclusively* as `OperatingSegmentsExcludingIntersegmentElimination`; omitting
that member hid 144 rows and made a three-segment company look segment-less,
which in turn made its false-premise records impossible to confirm.

Admitting a second qualifier creates a risk, so it is guarded. A company can
report the same segment and period under both members with different values -
one including intersegment sales, one not. A question naming only the segment
and the period cannot distinguish them, so `drop_conflicting` removes every
fact whose (company, concept, axis, member, unit, period) key carries more than
one distinct value rather than silently picking one. Identical values under both
qualifiers are kept.

Net effect: 7,486 facts to 7,200, with companies-reporting-segments rising from
48 to 52. Fewer facts, and the ones that remain answer exactly one question.

## Automated pre-check on false premises

A false-premise record is only correct if the segment it names genuinely does
not exist for that company. `finbench.false_premise` cross-checks all 38 against
the segment corpus and separates the ones where absence is positively confirmed
from the ones where it cannot be. It does not replace the human pass: absence
from this corpus is not absence from the filings. It concentrates the human pass
on the records that carry risk - currently 4 of 38, all single-segment
companies (WK Kellogg, Salesforce) with no business-segment facts to check
against.

Matching normalises both sides to bare alphanumerics before stripping the
`segment`/`member` boilerplate, because filings label a member "Med Tech
Segment" while the element is "MedTechMember" and a word-boundary regex cannot
see the suffix in the camel-case form. Substring matching also needs a length
floor on both sides: without it the geographic member "US" matches inside
"SafetyAndIndustrial" and every long segment name looks like a collision.

## Stock splits are not restatements

A stock split retroactively rewrites every prior-period per-share figure by a
clean integer ratio, so it surfaces in the restatement groupby looking exactly
like a recast. It is not one. The restatement track is about prior periods
superseded by later comparatives after spin-offs and divestitures; a split
question tests split-awareness instead, and blending the two would corrupt the
category.

The first gold build contained 9 such records out of 77: Amazon 20-for-1,
Salesforce 4-for-1, Danaher and Comcast 2-for-1, GE 1-for-8. The Amazon one is
recognisable on sight, and leaving it in the published set would invite a
reviewer to doubt the entire category.

`restatements.is_probable_split` now excludes them: a per-share-sensitive
concept whose revision ratio sits within 2% of a whole number between 2x and
60x. Non-per-share concepts are never treated as splits, so a revenue figure
that happens to double is still a restatement. The count stayed at 77 because
the next-ranked genuine restatements took the freed slots.

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

## Measured knowledge cutoffs

Elicited from each model at the start of the run (spec 7.4), three samples each,
on 2026-09-02 for $0.04.

| Model | Stated cutoff | Stable across 3 samples |
|---|---|---|
| `openai/gpt-5.6-sol` | 2024-06 | yes |
| `openai/gpt-5.6-luna` | 2024-06 | yes |
| `anthropic/claude-opus-5` | 2025-01 | yes |
| `google/gemini-3.1-pro-preview` | 2025-01 | yes |
| `x-ai/grok-4.6` | 2024-10 | **no - answered 2023-12 and 2024-10** |
| `perplexity/sonar-pro` | 2025-08 | yes |

The probe samples three times rather than once because single samples proved
unreliable: Gemini answered 2025-01 and then 2024-08 to identical calls at
temperature 0 during development, and Grok spans ten months across its three
samples. A model that cannot state its own cutoff consistently cannot reliably
know when to abstain, so this is reported as a finding rather than smoothed
into a single number.

## Why the post-cutoff bucket has two tiers

Taking each company's most recent filing produced 48 post-cutoff records that
were all post-cutoff for all six models, at gaps of 8-25 months, with 37 of the
48 ending in a single month. Valid, but every one of them "obviously recent" -
exactly the case spec 7.4 predicts models handle correctly - and the per-model
boundary machinery it mandates had nothing to do, because no question fell on
different sides for different models.

A second tier of 98 **boundary** records now spans 2024-01 to 2025-04, the
window the measured cutoffs actually fall in. They carry the true value, and
the harness decides per model whether abstention or the figure is correct:

| Model | Boundary records post-cutoff | Answerable |
|---|---|---|
| `gpt-5.6-sol` / `gpt-5.6-luna` | 49 | 49 |
| `claude-opus-5`, `gemini-3.1-pro` | 44 | 54 |
| `grok-4.6` | 47 | 51 |
| `sonar-pro` | 0 | 98 |

49 of the 98 have a different correct answer depending on which model is asked.
Those are the records that make the comparison in spec 7.4 mean anything.

## Question rendering

Gold records store fields, not sentences. `finbench.prompts` turns one into the
question an analyst would type, and two properties of that rendering are
enforced by tests rather than by care:

- A **false-premise** question goes through the same template as a real segment
  question, and a **post-cutoff** question through the same template as an
  answerable one. If the category were legible from the wording, the benchmark
  would measure trap detection instead of parametric recall.
- An unmapped XBRL tag raises. No question ever reaches a model reading
  "RevenueFromContractWithCustomerExcludingAssessedTax".

Company names are the EDGAR registrant strings verbatim with the ticker
appended, so `DANAHER CORP /DE/ (DHR)`. Title-casing them reads better and is a
transformation this project cannot verify; ambiguity about which registrant is
being asked costs more than typography.

### Segments that cannot be named

Carvana and Elanco tag a bare `ReportableSegmentMember` - the whole member name
is boilerplate - which rendered as "revenue in the  segment". Two buried
records were built on it. `is_unnameable_member` now drops those facts at build
time and `question_text` raises on one, so the failure cannot recur silently.
The gold count stayed at 358: the freed slots went to the next segment facts in
the surplus.

### The response schema

`answer`, `unit`, `confidence` (0-100), `abstain`, and a two-sentence free-text
`note`. Deliberately absent is any field asking whether the premise holds. Such
a field would appear on all 358 questions and tell every model to go looking
for a trick, which is a different measurement. The three-way false-premise
outcome (fabricated / abstained / correctly_rejected) is recovered at grading
time from `abstain` and `note`.

## How the frozen rules are applied

`config/grading.yaml` holds the thresholds; `finbench.grading` is the only
thing that reads them. Three readings of the config were decisions, so they are
recorded here.

**Stated precision AND the floor, not either.** A numeric answer is correct
only if it agrees with gold when both are rounded to the number of significant
figures the model stated, *and* its relative error is within 0.1%. Stated
precision alone would credit "about $100 billion" against 96,773,000,000, since
both round to the same single figure. The floor alone would credit a figure
whose extra digits are invented. The practical effect: a three-significant-
figure answer passes, a one- or two-figure answer does not.

Significant figures are counted off the digits the model wrote. Trailing zeros
on a whole number are not significant - a model answering 96800000000 is
claiming three digits, not eleven - which is the only reading available once
the schema asks for a plain number rather than "$96.8 billion".

**Scale errors are checked first.** A ratio within 1% of a power of 1000
classifies as a scale error even when the figure would otherwise round to gold.
Being off by a thousandfold is never correct, however well the digits line up.

**Format adherence is measured, not repaired.** `format_ok` is true only for a
bare JSON object: a code fence or a sentence of preamble is a schema violation
and is counted as one. A fallback parser still recovers the object from
anywhere in the response, so a violation scores as data rather than as a failed
call - which is the point of leaving the schema prompt-instructed.

**Rejecting a premise requires saying so.** Separating `correctly_rejected`
from `abstained` needs the model to name the reason, so a phrase list matched
against the `note` field decides it. The list is in the config file rather than
in code, and was committed before `results/` contained anything.

## Verification

<!-- Human-verified count filled in when the sheet is applied; abstention
     classification agreement rate on a random 100 at Milestone 4. -->

### Round 1: evidence pass, and the gold rebuild it forced

Before any human sign-off, an AI assistant checked all 78 sheet rows against
the filings and wrote proposed verdicts with evidence
(`data/verification_round1_proposed.csv`, `data/verification_round1_report.md`).
Those verdicts are evidence for the human pass, not the human pass: no record
is marked `verification: human` on their strength.

It proposed 74 correct and 4 wrong. None of the four was a wrong number. Every
one was the right number attached to the wrong period, and three of the four
traced to pipeline bugs rather than one-off bad rows. The gold set was
therefore rebuilt from the same cached data - before any benchmark question
was sent to a model - rather than patched row by row.

**Period labels came from the form type, not the dates.** Boundary records
were phrased from the filing's form: anything on a 10-K became "the fiscal
year ended", anything on a 10-Q "the three months ended". A 10-K carries
quarterly comparatives and a 10-Q carries year-to-date figures, so DuPont's
Q1 2024 revenue ($1.599B) was asked as a fiscal year, and Nike's nine-month
revenue ($38.8B) as a quarter. 13 of 98 boundary records were mislabeled
(a 14th, Costco's 12-week quarter, is now phrased in weeks); only 2 of the 13
were in the random sample, so a sample-only review would have passed the
other 11. Labels now come from each observation's own start and end.

**A twelve-month span is not necessarily a fiscal year.** Amazon's 10-Qs tag
trailing-twelve-month cash-flow figures ending September 30, and the
restatement track called one "the fiscal year ended September 30, 2016".
Every annual-length period is now checked against the company's fiscal
year-end from EDGAR submissions (`fiscalYearEnd`), with a week of tolerance
for 52/53-week filers, and rejected if it does not match.

**The notes data sets round period ends to month-end.** `ddate` is the nearest
month-end, so Costco's 12 weeks ended May 10, 2026 arrived as "the three months
ended April 30", a period Costco never reports. Segment facts now take their
exact dates from the same accession's non-dimensional facts in companyfacts;
a fact with no unique match is dropped (under 3% of segment revenue facts), never
guessed. 27 of 97 buried records changed as a result, almost all to the same
value with the true end date. Periods that a filer reports in weeks and that
are more than a week off a calendar quarter are now phrased in weeks.

**Two further defects the sample could not have caught.** "Segment
Eliminations" (Disney, -$643M) passed the generic-member filter, which only
matched labels *starting* with a reconciling word; a $0 Phillips 66 chemicals
row was also a buried question. Both are now filtered. And the false-premise
builder iterated a Python `set`, so the borrowed segment names depended on
`PYTHONHASHSEED`: two builds from identical data produced different records.
It is now sorted, and the post-cutoff age check uses a pinned date instead of
today, so the gold set is a pure function of the cached data. 20 of the 38
false-premise records changed in consequence.

The verification sheet was regenerated from the rebuilt set with the same
fixed seed. 52 of its 78 rows carry round-1 evidence for an unchanged record;
26 are new or changed and have none.
