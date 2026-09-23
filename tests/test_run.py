"""Plan construction and spend-cap abort, without hitting OpenRouter."""
from __future__ import annotations

import gzip
import json

from finbench import run
from finbench.clients import CallResult


QUESTION = {
    "question_id": "bur-x",
    "question": "What was Testco's total revenue for 2024?",
    "category": "buried",
    "answer_type": "numeric",
    "gold_value": 100.0,
    "gold_unit": "USD",
    "fiscal_period_end": "2024-12-31",
    "cik": 1,
    "company": "Testco",
    "concept": "Revenues",
}

MODEL_A = {"id": "aa", "slug": "lab/a", "provider_tags": ["lab"],
           "provider_names": ["Lab"], "send_temperature": True,
           "reasoning": None, "role": "flagship"}
MODEL_B = {**MODEL_A, "id": "bb", "slug": "lab/b"}


def _ok(text='{"answer": 100, "unit": "USD", "confidence": 80, "abstain": false, "note": ""}'):
    return CallResult(
        ok=True, model_id="aa", requested_slug="lab/a", temperature_sent=0.0,
        resolved_model="lab/a", resolved_provider="Lab", quarantined=False,
        quarantine_reason=None, text=text, prompt_tokens=10, completion_tokens=20,
        reasoning_tokens=None, cost_usd=0.5, latency_ms=12, error=None,
    )


def test_plan_is_questions_times_models_times_samples():
    plan = run.build_plan([QUESTION, {**QUESTION, "question_id": "bur-y"}],
                          [MODEL_A, MODEL_B], samples=3)
    assert len(plan) == 12
    assert {item["sample_idx"] for item in plan} == {0, 1, 2}


def test_limit_truncates_questions_not_samples():
    qs = [{**QUESTION, "question_id": f"q{i}"} for i in range(10)]
    plan = run.build_plan(qs, [MODEL_A], samples=3, limit=2)
    assert len(plan) == 6
    assert len({item["question"]["question_id"] for item in plan}) == 2


def test_a_short_pilot_is_not_the_first_category_only():
    # gold.jsonl is restatements first. A naive [:25] would never touch
    # false-premise or post-cutoff, which is exactly what a pilot is for.
    from finbench import gold
    from finbench.config import DATA_DIR
    records = gold.read(DATA_DIR / "gold.jsonl")
    picked = run.select_questions(records, 25, seed=0)
    cats = {r["category"] for r in picked}
    assert len(picked) == 25
    assert len(cats) >= 4


def test_dry_run_prints_counts_and_calls_nothing(capsys):
    plan = run.build_plan([QUESTION], [MODEL_A, MODEL_B], samples=3)
    code = run.execute(plan, client=None, raw_path=None, spend_cap=10,
                       dry_run=True, cutoffs={})
    assert code == 0
    out = capsys.readouterr().out
    assert "planned_calls=6" in out
    assert "aa" in out


def test_spend_cap_stops_further_calls(tmp_path):
    calls = {"n": 0}

    class Fake:
        def call(self, **_kw):
            calls["n"] += 1
            return _ok()

    plan = run.build_plan(
        [{**QUESTION, "question_id": f"q{i}"} for i in range(8)],
        [MODEL_A], samples=1,
    )
    raw = tmp_path / "raw.jsonl.gz"
    run.execute(plan, client=Fake(), raw_path=raw, spend_cap=1.0,
                dry_run=False, cutoffs={})
    # Each call costs $0.50; cap $1.00 should allow two then abort.
    assert calls["n"] == 2
    rows = [json.loads(line) for line in gzip.open(raw, "rt", encoding="utf-8")]
    assert len(rows) == 2
    assert all("text" in row for row in rows)
