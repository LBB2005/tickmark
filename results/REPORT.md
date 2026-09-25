# Tickmark closed-book results

Run `d849113d369c`: 358 questions × 6 models × 3 samples = 6,444 cells, all
answered. Gold carries a human verification pass (the 78-record seeded sample,
78/78 confirmed). Full generated tables are in [`TABLES.md`](TABLES.md), and
machine-readable output is in [`summary.json`](summary.json). Intervals are
Wilson 90%.

**Headline: confident-wrong. Control: numeric accuracy.** A confident-wrong
answer gives a figure, at confidence 75 or higher, that the filing contradicts.
That is the answer an analyst is most likely to trust and copy.

## Results

| Model | Confident-wrong | Numeric accuracy | Fabrication (false premise) |
|---|---|---|---|
| gpt-5.6-luna (cheap tier) | **20.8%** (223/1074; 18.8–22.9) | 2.5% (17/669; 1.7–3.7) | 0.0% (0/114) |
| gpt-5.6-sol | 5.5% (59/1074; 4.5–6.8) | 11.5% (77/669; 9.6–13.7) | 0.0% (0/114) |
| claude-opus-5 | 0.3% (3/1074; 0.1–0.7) | 9.2% (63/684; 7.5–11.2) | 0.0% (0/114) |
| gemini-3.1-pro | 0.2% (2/1074; 0.1–0.6) | 2.5% (17/684; 1.7–3.7) | 0.0% (0/114) |
| grok-4.6 | 0.1% (1/1074; 0.0–0.4) | 4.4% (30/675; 3.3–5.9) | 0.0% (0/114) |
| *sonar-pro (retrieval reference, see below)* | *36.2% (389/1074; 33.8–38.7)* | *58.6% (478/816; 55.7–61.4)* | *4.4% (5/114; 2.2–8.7)* |

All six models returned the schema-conforming JSON on at least 99.4% of calls.

## What the numbers say

**1. The cheap tier is confidently wrong about one time in five, and at the
extreme it is almost never unsure.** gpt-5.6-luna answered 216 of 669 numeric
questions and got 17 right. It gave **14.7%** of all its answers
(158/1074; 13.0–16.6) at confidence 90 or higher while wrong. Its mean
confidence was 87 when wrong and 98 when right, so its stated confidence
barely separates the two.

**2. The tier gap is calibration, not knowledge.** gpt-5.6-sol, the flagship of
the same generation, knows more (11.5% accuracy vs 2.5%) but not dramatically
more. What separates them is what each does when it doesn't know. sol answered
more questions (362) yet was confidently wrong far less often, because its
confidence when wrong averaged 50, not 87. Pairing the two models within one
generation (spec 7.1) is what allows this reading: the gap is a trained
behaviour, not an older model versus a newer one.

**3. The traps are handled; the plausible questions are not.** Every
closed-book model scored **0 confident-wrong** on buried segment figures,
false-premise segments and post-cutoff periods, and **0 fabrications** across
114 false-premise questions each. All confident errors fall in the two
categories where a plausible figure exists in training data:

| Confident-wrong | Post-cutoff boundary | Restatement |
|---|---|---|
| gpt-5.6-luna | 43.9% (129/294; 39.2–48.7) | 40.7% (94/231; 35.5–46.1) |
| gpt-5.6-sol | 17.0% (50/294; 13.7–20.9) | 3.9% (9/231; 2.3–6.6) |
| claude-opus-5 | 1.0% (3/294) | 0.0% (0/231) |
| gemini-3.1-pro | 0.0% (0/294) | 0.9% (2/231) |
| grok-4.6 | 0.0% (0/294) | 0.4% (1/231) |

Restatement asks for a figure a company later revised. The model has usually
memorised the original, answers it, and is sure of it. The boundary category
asks for a period close to the model's own stated training cutoff, where a
confident answer usually means filling a gap.

**4. The flagships answer, but hedge.** Near the cutoff, claude-opus-5 and
gpt-5.6-sol give figures they cannot know: 129 and 142 of 294 boundary answers
fall after their own stated cutoffs. Of claude-opus-5's 234 wrong or
out-of-cutoff boundary answers, only 3 came at confidence 75 or higher; for
gpt-5.6-sol it was 50 of 220. Most of the time, an analyst reading the
confidence field would be warned. Gemini and Grok
mostly decline (false-refusal rates of 96.5% and 89.9% on numeric questions).
That is safe, and also nearly useless as recall.

## The retrieval reference line (sonar-pro)

sonar-pro searches the web natively, so it is reported in its own row and
never compared with the closed-book models. Two things about its numbers need
saying.

**Perplexity changed its behaviour behind the same model name.** In the
working run (2026-09-18), sonar-pro followed the closed-book instruction and
abstained on 89% of questions ("I do not have access to up-to-date filings").
In this run, with an identical prompt, identical token counts and the same
resolved model and provider, it answers from search, abstaining on 16% and
reaching 58.6% numeric accuracy. On the 260 questions identical across both
runs, its confident-wrong rate went from 4.1% to 42.7% (z = 18). The
substitution check cannot catch this, because the reported model name did not
change. Treat sonar-pro's row as a measurement of Perplexity's behaviour in the
week of 2026-09-23, and nothing longer-lived.

**Its headline rate is inflated by a scoring rule written for closed-book
models.** Post-cutoff questions are scored "must abstain": a closed-book model
cannot know the figure, so any answer is invented. sonar-pro can search for it,
and 144 of its 389 confident-wrong answers are post-cutoff questions answered
from search. Those answers may well be correct, and they cannot be graded,
because post-cutoff gold is null by design. The frozen rule is kept as it
stands, since changing a grading rule after seeing results is exactly what this
project forbids. On gradable numeric questions only, sonar-pro's confident-wrong
rate is **29.4%** (240/816; 26.9–32.1). Most of that is restatements (164/231):
search finds the originally reported figure and returns it with high
confidence.

## Reproducibility

The closed-book results reproduce. On the **260 questions identical in text
and gold** between the working run (2026-09-18) and this one (2026-09-23/25),
no closed-book model's confident-wrong rate, accuracy or abstention rate moved
by more than |z| = 1.4:

| Model | Confident-wrong | Numeric accuracy | Abstention |
|---|---|---|---|
| claude-opus-5 | 0.1% → 0.0% | 1.2% → 1.1% | 68.2% → 69.5% |
| gemini-3.1-pro | 0.0% → 0.3% | 0.0% → 0.0% | 88.3% → 87.7% |
| gpt-5.6-luna | 11.3% → 12.1% | 0.0% → 0.0% | 82.1% → 81.5% |
| gpt-5.6-sol | 1.8% → 1.2% | 1.3% → 1.5% | 65.1% → 65.4% |
| grok-4.6 | 0.1% → 0.1% | 0.4% → 0.2% | 86.4% → 87.4% |

## Changes since the working run `dfba4ccd2d88`

| Model | Confident-wrong, working run | Confident-wrong, this run |
|---|---|---|
| gpt-5.6-luna | 19.7% | 20.8% |
| gpt-5.6-sol | 5.7% | 5.5% |
| claude-opus-5 | 0.6% | 0.3% |
| gemini-3.1-pro | 0.0% | 0.2% |
| grok-4.6 | 0.1% | 0.1% |
| sonar-pro | 6.4% | 36.2% (see above) |

The table above shows the closed-book models themselves did not change, so the
shifts here come from the benchmark:

- **98 boundary questions were reworded** to "As most recently reported by…".
  13 of them had carried a figure the company later recast, and a model
  answering the as-filed figure was scored wrong (METHODOLOGY, *Figures the
  company has since recast*).
- **62 gold records were rebuilt** after round-1 verification fixed period
  labels.
- **Gold was verified**, and **coverage is now complete.** The working run
  left 8 timeouts unscored; here every failed call was retried once and
  recovered.

## Run record

| | |
|---|---|
| Run | `d849113d369c`, config hash `3aa4c2f9237198ec` (single hash across all rows) |
| Dates (UTC) | 2026-09-23 for the first 3,924 cells; 2026-09-25 for the remaining 2,520 |
| Coverage | 6,444 / 6,444 cells; 4 dropped connections, all recovered on retry; 0 substitutions |
| Cost | $19.91 for the run; $21.40 in total including the pilot and probes |
| Gold | 358 records; 78 `human` (seeded sample, 78/78 confirmed), 280 `auto` |

The run stopped at 61% when the OpenRouter account ran out of credits, and was
resumed under the same config after a top-up. The harness refuses to resume
when the config hash differs. Every one of the 5,075 out-of-credits attempts
is kept in the raw file as an audit trail; none is counted in any rate. Pilot rows
(`329bdd9a3e75`) were a gate only and are not included.

## Limits

- **Calibration metrics include abstentions.** ECE, Brier and confidence AUC
  (in `TABLES.md`) are computed over every scored row, including abstentions.
  For an abstention, the confidence field is ambiguous: models report 100 to
  mean "sure that declining is right". These three metrics are therefore
  indicative only. The confident-wrong rates above count only committed
  answers and are not affected.
- **280 of 358 gold records are unverified** beyond the automated pipeline. In
  the seeded sample, with 9 buried rows and zero defects, the one-sided 95%
  upper bound on the buried-category defect rate is about 28%.
- **Category-level n is modest** (114–294 per model), and the intervals above
  are wide enough to matter.
- **Not in this round:** the reasoning-toggle subset (built, not run, for
  cost), the open-book track, covenant questions, and the Milestone-4
  hand-check of abstention classification on a random 100.
