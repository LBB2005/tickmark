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

## Verification

<!-- Filled in at Task 1.9 and Milestone 4: human-verified count, and the
     abstention classification agreement rate on a random 100. -->
