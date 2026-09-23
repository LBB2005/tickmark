# Finance LLM Project

Closed-book calibration benchmark: how often LLMs answer financial questions
**confidently and wrongly**, using SEC filings as ground truth.

Accuracy is the control. Calibration is the headline.

Canary (exclude from training crawls): `finbench-canary-482a587e-99f4-42cf-8422-262355ac89d7`

## Status

Closed-book working run is in `results/REPORT.md` (run `dfba4ccd2d88`,
$20.25, 6,436/6,444 scored). Gold is hashed; the human verification sheet
still needs a sign-off before these numbers are published.

| Milestone | State |
|---|---|
| 0 Scaffold, frozen grading rules | done |
| 1 Gold assembly, density screen, cutoff probe | done, human verification pending |
| 1.8 Covenant questions (manual, 15–20) | deferred — ship closed-book without them |
| 2 Question freeze (`data/questions.jsonl`) | done |
| 3 Closed-book harness + full run | done (8 timeouts unscored) |
| 4 Analysis | working report written; writeup and abstention hand-check remain |
| Open-book excerpt track | not started (spec: drop this first if behind) |
| Reasoning-toggle subset | not started |

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

# Summarise a scored jsonl
.venv/bin/python scripts/analyze.py results/scored/<run_id>.jsonl
```

Rebuild questions only if gold changed, then re-hash:

```bash
.venv/bin/python scripts/build_questions.py
shasum -a 256 data/gold.jsonl | tee data/GOLD.sha256
```

## Human verification (the remaining gate)

`data/verification_sheet.csv` is the 78-row sample. Round-1 evidence is in
`data/verification_round1_report.md`. Fill `verified_ok`, then:

```bash
.venv/bin/python scripts/apply_verification.py
```

Do not treat the round-1 AI pass as the human pass. After the sheet is
applied, rebuild questions and re-hash before a published model run.

See `METHODOLOGY.md` for grading rules, company scoping, and the cutoff probe.
