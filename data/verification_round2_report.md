# Gold verification report — round 2

**This is an AI pass. It is evidence, not the human verification gate.**
README and `src/finbench/false_premise.py` both state that an automated pass
cannot stand in for the human one. Nothing here licenses marking any record
`verification: human`, and `data/verification_sheet.csv` still has
`verified_ok` empty on all 78 rows. All 358 gold records remain
`verification: auto`.

Ten agents with distinct briefs read primary SEC filing HTML — deliberately not
`companyfacts`, the notes datasets, or `data/cache/`, since gold was built from
those and checking gold against them is circular. Round 1 did verify against
`companyfacts` and said so (`verification_round1_report.md:31`); that did not
recur here.

## 1. What the row pass returned

| Agent | rows | y | n | unsure |
|---|---:|---:|---:|---:|
| segment-auditor-A/B/C (false_premise) | 38 | 38 | 0 | 0 |
| literalist (buried) | 9 | 9 | 0 | 0 |
| boundary-analyst (post_cutoff_boundary) | 15 | 15 | 0 | 0 |
| restatement-historian | 7 | 7 | 0 | 0 |
| cutoff-clerk (post_cutoff) | 9 | 9 | 0 | 0 |
| skeptic (26 cold/stale rows, adversarial) | 26 | 24 | 2 | 0 |

77 of 78 `direct_url`s were genuinely fetched; both legs of all 7 restatement
pairs were opened. The one gap is `pcb-IBM-2024-03-31`, verified from a later
filing's comparative column rather than its own as-filed document.

## 2. The finding

Seven of eight row agents returned `y` on the boundary category. The skeptic
dissented on two rows, the red team confirmed it and found two more. The
underlying defect is larger than any of them reported and is a **builder bug**,
not bad rows.

`scripts/build_gold.py:283-285` keeps the **latest-filed** value for a period,
so a boundary record carries the figure as *recast*, while
`src/finbench/prompts.py` rendered the bare question *"What was X's revenue for
period P?"*. The `"As most recently reported by"` qualifier was applied only to
`restatement`. By the codebase's own comment, that phrase "is what makes
answering the original figure a miss rather than a defensible reading" — so
without it these questions graded a defensible reading as a miss, in the
direction that **inflates confident-wrong**, the headline this project reports.

**13 of 98 boundary records** name a figure the company has since restated.
Full list with both values in `data/verification_round2_divergent.csv`.
Deltas run −9% to −53%; every one is a 2024–26 separation (GE/Vernova,
3M/Solventum, DuPont/Qnity, Baxter/Vantive, Fortive/Ralliant, BD/Waters,
Honeywell/Solstice, AIG, News Corp, WDC/SanDisk).

Only 4 of the 13 are in the 78-row sample. **9 were invisible to it.**

### How the count was established

Three independent tests disagreed, and the disagreements were the useful part:

| Test | Count | Missed |
|---|---:|---|
| Text presence in as-filed filing | 12 | `pcb-WDC-2024-03-29` |
| Methodologist's independent sweep | 12 | `pcb-MMM-2024-03-31` |
| **Family-aware multi-accession facts** | **13** | — |

- **WDC** defeated the text test: gold's `4,313` *does* appear in the as-filed
  10-Q — as the **HDD segment** line, while consolidated revenue was `9,239`.
  A coincidental string match.
- **3M** defeated a per-concept test: the recast **crossed tags**. `Revenues`
  for Q1 2024 went `8,003M` (as-filed) → `6,016M` (recast), while gold's
  `RevenueFromContractWithCustomer...` only ever held `6,016M`. Checking inside
  gold's own concept sees one value and calls it stable.

The authoritative test compares every value the company reported for the span
across **all accessions and across interchangeable revenue tags**. Using the
API here is not circular: the question is not "is gold right" but "did the
company report two different numbers", which the API records faithfully because
each fact carries its own accession. 4 further hits (Berkshire ×2, Capital One
×2) were dual-tagging at identical values and are excluded.

## 3. The fix

Applied: `prompts.py` now renders the `"As most recently reported by"` prefix
for `post_cutoff_boundary` as well as `restatement` (`RECAST_AMBIGUOUS`).

Applied to the **whole category**, not just the 13. Wording that varied with
whether a record happened to be recast would make the answer legible from the
question, which spec 6.1 forbids. Two regression tests pin this, including one
asserting boundary and restatement render identically.

Gold values are unchanged; 98 questions re-rendered; `questions.jsonl` rebuilt
and re-hashed. No row was hand-edited — `a36c64e` is the precedent.

## 4. Measured impact on the existing run

Small, and in the reassuring direction. Confident-wrong on the divergent
records (11.6%) is statistically indistinguishable from the other 86 boundary
records (12.1%), so this was **not** inflating the headline. Excluding the
affected records moves the worst-case model by −1.1pt (`gpt-5.6-luna`
19.7% → 18.6%); every other model moves ≤0.1pt. The result survives; the
records were still wrong and are still worth fixing.

## 5. Defects in this pass, recorded against it

- **Confabulated evidence.** The boundary-analyst claimed on all 15 of its rows
  to have read "the inline-XBRL fact behind the number ... its concept and its
  actual context start/end dates". The helper strips every tag before caching,
  so `contextRef` appears in 0 of 81 cached files. Those specific claims are
  unsupported by the tool used — and they land on the two contestable
  judgement calls in the set (Baxter lease revenue, Costco membership fees),
  both resolved in gold's favour by citing a tag the agent could not see. The
  conclusions may be right; the evidence is invented. Disregard it.
- **Seven of eight agents missed the finding.** The one that caught it was
  prompted to attack rather than confirm. That is a prompt effect, not a
  consensus — eight subagents of one model are not eight independent checkers.
  Majority vote would have buried the only true finding 7–1.
- **Instrument defect, since fixed.** `c372131` populated `direct_url` for
  boundary rows by period-matching, pointing verifiers at a filing that
  *contradicts* the value they were asked to confirm. Any honest verifier
  following that instruction had to write `n`. That is what the skeptic
  actually detected. `direct_url` now points at gold's own source, with the
  as-filed document carried alongside in `as_filed_url`.
- **`pcb-IBM-2024-03-31`** was never opened in its own right. Open it.

## 6. Live hazard, not yet addressed

`scripts/apply_verification.py` stamps `verification="human"` unconditionally
for every `y` row and takes the verifier name from `argv` or `$USER`. Nothing
in it knows who filled the sheet. If these AI verdicts were pasted into
`verified_ok` and the script run, gold would silently acquire ~76
"human-verified" records that no human saw, and `gold.py` admits only
`{"auto", "human"}` — there is no third state to fall back to. Adding an
`ai_reviewed` value, not publishable, is the schema change that would make
recording a pass like this one safe. **Left for a human decision.**

## 7. What a human still has to do

The 78-row sheet is unchanged and unsigned. This pass narrows the job rather
than removing it. Priority order:

1. The **9 unsampled divergent records** — now disambiguated by the wording fix,
   but nobody has looked at them.
2. The 4 sampled divergent rows (AIG, BAX, DD, HON).
3. `pcb-IBM-2024-03-31`.
4. The concept-mapping judgement calls on Baxter and Costco, whose supporting
   evidence was confabulated and must be redone.
5. The remaining 73 rows, where the sheet now carries a direct filing link.

With n=9 and zero defects found, the one-sided 95% upper bound on the `buried`
defect rate is ~28%. Nine clean rows is not a clean category.
