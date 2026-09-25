# Finance LLM Project

Closed-book calibration benchmark: how often LLMs answer financial questions
**confidently and wrongly**, using SEC filings as ground truth.

Accuracy is the control. Calibration is the headline.

Canary (exclude from training crawls): `finbench-canary-482a587e-99f4-42cf-8422-262355ac89d7`

## Status

Closed-book results are in [`results/REPORT.md`](results/REPORT.md) (run
`d849113d369c`: 6,444/6,444 cells, $19.91). Headline: the cheap tier
(gpt-5.6-luna) is confidently wrong on 20.8% of questions against 0.1–5.5% for
the flagships, and every closed-book error falls on restatement and
near-cutoff questions. Gold carries a human verification pass on the seeded
sample.

| Milestone | State |
|---|---|
| 0 Scaffold, frozen grading rules | done |
| 1 Gold assembly, density screen, cutoff probe | done; human verification done (78/78 on the seeded sample) |
| 1.8 Covenant questions (manual, 15–20) | deferred: shipped closed-book without them |
| 2 Question freeze (`data/questions.jsonl`) | done; boundary questions reworded after round-2 verification |
| 3 Closed-book harness + full run | done: full coverage, retry pass, resumable |
| 4 Analysis | report written; abstention hand-check (random 100) remains |
| Open-book excerpt track | not started (spec: drop this first if behind) |
| Reasoning-toggle subset | built and tested, not run (cost) |

## Setup

```bash
git clone https://github.com/LBB2005/Finance-LLM-Project.git
cd Finance-LLM-Project
uv sync --extra dev
cp .env.example .env   # then set OPENROUTER_API_KEY
```

`OPENROUTER_API_KEY` is copied from `~/code/The AEO Portfolio Index/.env`.
SEC requests need `SEC_CONTACT_EMAIL`.

## Run

```bash
# Plan only — no API calls
.venv/bin/python -m finbench.run --dry-run

# Spec gate: 25-question stratified pilot across the roster, 3 samples
.venv/bin/python -m finbench.run --limit 25 --spend-cap 10 --concurrency 4

# Full closed-book run (~$20; 358 questions × 6 models × 3 samples)
.venv/bin/python -m finbench.run --spend-cap 40 --concurrency 4

# Continue a run that stopped (spend cap, out of credits): same args plus
.venv/bin/python -m finbench.run --resume <run_id> --spend-cap 15

# Reasoning-toggle subset (claude-opus-5, 60 q, reasoning on; ~$1-6)
.venv/bin/python -m finbench.run --track reasoning_toggle --spend-cap 9

# Summarise -> results/summary.json + results/TABLES.md (REPORT.md is hand-written)
.venv/bin/python scripts/analyze.py results/scored/<run_id>.jsonl
```

Rebuild questions only if gold changed, then re-hash:

```bash
.venv/bin/python scripts/build_questions.py
shasum -a 256 data/gold.jsonl | tee data/GOLD.sha256
```

## Human verification

Done: the 78-row seeded sample (`data/verification_sheet.csv`) was checked
against the primary filings by a human, and all 78 records were confirmed and
marked `verification: human`. The other 280 are `auto` by design.

Two AI evidence passes came first: `data/verification_round1_report.md` and
`data/verification_round2_report.md`. Round 2 found 13 boundary records
carrying figures the company later recast, which led to the "As most recently
reported by" wording fix. Neither AI pass marked anything `human`.

To re-apply after editing the sheet:

```bash
.venv/bin/python scripts/apply_verification.py "Your Name"
```

Pass your name explicitly. The script marks every `y` row `human` and
otherwise records `$USER`, so it cannot tell who actually filled in the sheet.
Rebuild questions and re-hash afterwards.

See `METHODOLOGY.md` for grading rules, company scoping, and the cutoff probe.
