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

### The single-axis rule

Only facts dimensioned on **exactly one** axis are used. A row dimensioned on
`BusinessSegments` *and* `ProductOrService` is a product line inside a segment,
not the segment: both would answer "what was the X segment's revenue"
differently, which is the genuine-ambiguity failure mode the adversarial review
exists to catch. Rows carrying a `coreg` value are also dropped, since those
report a co-registrant subsidiary's books rather than the parent's.

Measured on the 2026_07 file: 2,349 raw segment-revenue rows for the candidate
universe collapse to 108 unambiguous ones. The strictness is the point.

Geographic facts (`Geographical` axis) are kept alongside business segments and
supply the `deep` difficulty tier.

## Verification

<!-- Filled in at Task 1.9 and Milestone 4: human-verified count, and the
     abstention classification agreement rate on a random 100. -->
