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


def _fail():
    return CallResult(
        ok=False, model_id="aa", requested_slug="lab/a", temperature_sent=None,
        resolved_model=None, resolved_provider=None, quarantined=True,
        quarantine_reason="request_failed", text=None, prompt_tokens=None,
        completion_tokens=None, reasoning_tokens=None, cost_usd=None,
        latency_ms=300000, error="The read operation timed out",
    )


def _substituted():
    return CallResult(
        ok=True, model_id="aa", requested_slug="lab/a", temperature_sent=0.0,
        resolved_model="lab/other", resolved_provider="Lab", quarantined=True,
        quarantine_reason="model_substituted:lab/other", text="{}",
        prompt_tokens=10, completion_tokens=5, reasoning_tokens=None,
        cost_usd=0.01, latency_ms=12, error=None,
    )


class Scripted:
    """Answers from a per-question script; records every call's kwargs."""

    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []

    def call(self, **kw):
        self.calls.append(kw)
        text = kw["messages"][-1]["content"]
        for qid, results in self.script.items():
            if qid in text and results:
                return results.pop(0)() if len(results) > 1 else results[0]()
        return _ok()


def _q(qid):
    return {**QUESTION, "question_id": qid, "question": f"Q about {qid}?"}


def _rows(raw):
    return [json.loads(line) for line in gzip.open(raw, "rt", encoding="utf-8")]


def test_transport_failure_is_retried_exactly_once(tmp_path):
    # The last full run left 8 timeouts unscored. One retry recovers them
    # without letting a persistently failing endpoint loop forever.
    client = Scripted({"q-flaky": [_fail, _ok]})
    plan = run.build_plan([_q("q-flaky"), _q("q-fine")], [MODEL_A], samples=1)
    raw = tmp_path / "raw.jsonl.gz"
    code = run.execute(plan, client=client, raw_path=raw, spend_cap=10,
                       dry_run=False, cutoffs={})
    rows = _rows(raw)
    flaky = [r for r in rows if r["question_id"] == "q-flaky"]
    assert [r["attempt"] for r in flaky] == [1, 2]
    assert flaky[0]["ok"] is False and flaky[1]["ok"] is True
    assert len(client.calls) == 3
    assert code == 0  # recovered, so nothing is still failing


def test_persistent_failure_is_not_retried_twice(tmp_path):
    client = Scripted({"q-dead": [_fail]})
    plan = run.build_plan([_q("q-dead")], [MODEL_A], samples=1)
    raw = tmp_path / "raw.jsonl.gz"
    code = run.execute(plan, client=client, raw_path=raw, spend_cap=10,
                       dry_run=False, cutoffs={})
    assert len(client.calls) == 2
    assert [r["attempt"] for r in _rows(raw)] == [1, 2]
    assert code == 1


def test_substitution_quarantine_is_data_not_noise_and_never_retried(tmp_path):
    # A resolved/requested mismatch says something about routing. Re-sending
    # it until it lands on the right model would hide exactly that.
    client = Scripted({"q-sub": [_substituted]})
    plan = run.build_plan([_q("q-sub")], [MODEL_A], samples=1)
    raw = tmp_path / "raw.jsonl.gz"
    run.execute(plan, client=client, raw_path=raw, spend_cap=10,
                dry_run=False, cutoffs={})
    assert len(client.calls) == 1


def test_spend_cap_blocks_the_retry_pass(tmp_path):
    # q0 fails for free; q1 and q2 cost $0.50 each and hit the $1.00 cap.
    # The retry must not spend past the cap the user set.
    client = Scripted({"q0": [_fail, _ok]})
    plan = run.build_plan([_q("q0"), _q("q1"), _q("q2")], [MODEL_A], samples=1)
    raw = tmp_path / "raw.jsonl.gz"
    run.execute(plan, client=client, raw_path=raw, spend_cap=1.0,
                dry_run=False, cutoffs={})
    assert len(client.calls) == 3
    assert all(r["attempt"] == 1 for r in _rows(raw))


def test_rows_carry_track_and_arm():
    plan = run.build_plan([_q("q1")], [MODEL_A], samples=1)
    assert plan[0].get("track", "closed_book") == "closed_book"


def test_model_max_tokens_overrides_the_default(tmp_path):
    client = Scripted({})
    big = {**MODEL_A, "max_tokens": 4000}
    plan = run.build_plan([_q("q1")], [big], samples=1)
    run.execute(plan, client=client, raw_path=tmp_path / "r.jsonl.gz",
                spend_cap=10, dry_run=False, cutoffs={},
                defaults={"temperature": 0, "max_tokens": 700})
    assert client.calls[0]["max_tokens"] == 4000


def test_reasoning_toggle_plan_is_sixty_questions_on_opus_with_reasoning_on():
    from finbench import config
    from finbench.gold import read
    questions = read(config.DATA_DIR / "questions.jsonl")
    plan = run.build_toggle_plan(questions, config.models())
    assert len(plan) == 60 * 3
    assert len({i["question"]["question_id"] for i in plan}) == 60
    for item in plan:
        assert item["track"] == "reasoning_toggle"
        assert item["arm"] == "on"
        # Same model id as the main run, so scoring finds Opus's stated
        # cutoff and the off arm pairs on (question_id, model_id, sample_idx).
        assert item["model"]["id"] == "claude-opus-5"
        assert item["model"]["reasoning"] == {"enabled": True}
        assert item["model"]["max_tokens"] > 700


def test_toggle_subset_is_reproducible_and_category_stratified():
    from finbench import config
    from finbench.gold import read
    questions = read(config.DATA_DIR / "questions.jsonl")
    a = run.build_toggle_plan(questions, config.models())
    b = run.build_toggle_plan(questions, config.models())
    assert [i["question"]["question_id"] for i in a] == \
           [i["question"]["question_id"] for i in b]
    assert len({i["question"]["category"] for i in a}) >= 4
