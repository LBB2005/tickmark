"""Closed-book evaluation harness (spec section 7).

Raw responses are gzipped JSONL, flushed per call: a killed job keeps
everything already paid for. Scoring is derived from those rows and the
frozen gold fields on each question, so it can be recomputed without a
re-run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import pathlib
import random
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from . import config, grading, prompts, scoring
from .clients import OpenRouterClient

ROOT = config.ROOT
RAW_DIR = ROOT / "results" / "raw"
SCORED_DIR = ROOT / "results" / "scored"


def roster(cfg: dict[str, Any] | None = None, *, include_reference: bool = True) -> list[dict]:
    cfg = cfg or config.models()
    models = list(cfg["models"])
    if include_reference:
        models.extend(cfg.get("reference_line") or [])
    return models


def load_cutoffs(path: pathlib.Path | None = None) -> dict[str, str | None]:
    """Stated cutoffs from the probe file, falling back to models.yaml."""
    cutoffs: dict[str, str | None] = {}
    for model in roster(include_reference=True):
        cutoffs[model["id"]] = model.get("stated_cutoff")
    probe = path or (config.DATA_DIR / "cutoff_probe.jsonl")
    if probe.exists():
        for line in probe.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("stated_cutoff"):
                cutoffs[row["model_id"]] = row["stated_cutoff"]
    return cutoffs


def select_questions(
    questions: list[dict[str, Any]],
    limit: int | None,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Take a category-stratified sample.

    gold.jsonl is restatements first. A naive slice would make every short
    pilot a restatement-only measurement, which cannot check parse rate on
    false-premise or post-cutoff questions.
    """
    if limit is None or limit >= len(questions):
        return list(questions)
    rng = random.Random(seed)
    by_cat: dict[str, list] = defaultdict(list)
    for question in questions:
        by_cat[str(question.get("category") or "none")].append(question)
    pools = []
    for category in sorted(by_cat):
        items = list(by_cat[category])
        rng.shuffle(items)
        pools.append(items)
    chosen: list[dict[str, Any]] = []
    while len(chosen) < limit and any(pools):
        for pool in pools:
            if pool and len(chosen) < limit:
                chosen.append(pool.pop())
    return chosen


def build_plan(
    questions: list[dict[str, Any]],
    models: list[dict[str, Any]],
    samples: int = 3,
    limit: int | None = None,
    model_ids: list[str] | None = None,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Every (question, model, sample) triple, in a stable order."""
    questions = select_questions(questions, limit, seed=seed)
    if model_ids is not None:
        wanted = set(model_ids)
        models = [m for m in models if m["id"] in wanted]
    plan = []
    for question in questions:
        for model in models:
            for sample_idx in range(samples):
                plan.append({
                    "question": question,
                    "model": model,
                    "sample_idx": sample_idx,
                })
    return plan


def build_toggle_plan(
    questions: list[dict[str, Any]],
    cfg: dict[str, Any],
    samples: int | None = None,
) -> list[dict[str, Any]]:
    """The reasoning-on arm of the spec 7.7 toggle.

    Only the ON arm is called. The OFF arm is the main run's own rows for the
    same model and questions: same day, same config, reasoning already off, so
    calling it again would pay twice for a measurement already held.

    The model keeps its main-run id so scoring finds its stated cutoff and the
    two arms pair on (question_id, model_id, sample_idx). The arm is carried on
    the row instead.
    """
    tcfg = cfg["reasoning_toggle"]
    base = next(m for m in cfg["models"] if m["id"] == tcfg["model_id"])
    on_model = {**base, "reasoning": tcfg["on"],
                "max_tokens": tcfg["max_tokens_on"]}
    samples = samples if samples is not None else cfg["sampling"]["samples_per_question"]
    chosen = select_questions(questions, tcfg["subset_size"], seed=tcfg.get("seed", 0))
    return [
        {"question": q, "model": on_model, "sample_idx": i,
         "track": "reasoning_toggle", "arm": "on"}
        for q in chosen for i in range(samples)
    ]


def cell_key(question_id: str, model_id: str, sample_idx: int,
             track: str | None = None, arm: str | None = None) -> tuple:
    return (question_id, model_id, sample_idx, track or "closed_book", arm)


def _item_key(item: dict[str, Any]) -> tuple:
    return cell_key(item["question"]["question_id"], item["model"]["id"],
                    item["sample_idx"], item.get("track"), item.get("arm"))


def out_of_credits(result: Any) -> bool:
    """A 402 is the account running dry, not the model or the network.

    Nothing about it improves on a retry, and every further call will fail the
    same way - run d849113d369c sent ~5,000 of them before this existed.
    """
    return (not result.ok) and str(result.error or "").startswith("402")


def resume_plan(
    plan: list[dict[str, Any]], rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple, int]]:
    """The part of `plan` an interrupted run has not yet answered.

    A cell is done once any attempt came back ok - including a substitution
    quarantine, which is a result, not a gap. Failed cells are re-run, with
    attempt numbers continuing from where the run stopped so the raw file stays
    a complete, ordered history of every call made.
    """
    done: set[tuple] = set()
    last: dict[tuple, int] = {}
    for row in rows:
        key = cell_key(row["question_id"], row["model_id"], row["sample_idx"],
                       row.get("track"), row.get("arm"))
        last[key] = max(last.get(key, 0), row.get("attempt") or 1)
        if row.get("ok"):
            done.add(key)
    remaining = [item for item in plan if _item_key(item) not in done]
    next_attempt = {key: n + 1 for key, n in last.items() if key not in done}
    return remaining, next_attempt


def _print_plan(plan: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for item in plan:
        counts[item["model"]["id"]] = counts.get(item["model"]["id"], 0) + 1
    print(f"planned_calls={len(plan)}")
    for model_id, n in sorted(counts.items()):
        print(f"  {model_id:<16} {n:>6}")


def execute(
    plan: list[dict[str, Any]],
    *,
    client: Any,
    raw_path: pathlib.Path | None,
    spend_cap: float,
    dry_run: bool,
    cutoffs: dict[str, str | None],
    defaults: dict[str, Any] | None = None,
    scored_path: pathlib.Path | None = None,
    concurrency: int = 1,
    append: bool = False,
    attempts: dict[tuple, int] | None = None,
) -> int:
    """Run the plan. Default concurrency is 1 so the spend cap is exact."""
    defaults = defaults or config.models().get("defaults") or {
        "temperature": 0, "max_tokens": 700,
    }
    if dry_run:
        _print_plan(plan)
        return 0

    if raw_path is None:
        raise ValueError("raw_path is required unless dry_run")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if scored_path is not None:
        scored_path.parent.mkdir(parents=True, exist_ok=True)

    run_date = dt.datetime.now(dt.timezone.utc).isoformat()
    cost = 0.0
    ok = failed = quarantined = 0
    lock = threading.Lock()
    aborted = {"flag": False, "reason": None}
    attempts = attempts or {}

    scored_fh = None
    if scored_path is not None:
        scored_fh = scored_path.open("a" if append else "w", encoding="utf-8")

    def one(item: dict[str, Any], attempt: int | None = None) -> Any:
        if attempt is None:
            attempt = attempts.get(_item_key(item), 1)
        nonlocal cost, ok, failed, quarantined
        with lock:
            if aborted["flag"] or cost >= spend_cap:
                aborted["flag"] = True
                aborted["reason"] = aborted["reason"] or f"spend cap ${spend_cap:.2f} reached"
                return None
        model = item["model"]
        question = item["question"]
        result = client.call(
            model=model,
            messages=prompts.build_messages(question),
            temperature=defaults.get("temperature", 0),
            max_tokens=model.get("max_tokens", defaults.get("max_tokens", 700)),
        )
        parsed = grading.parse_response(result.text or "")
        grade = scoring.grade(
            question, parsed,
            stated_cutoff=cutoffs.get(model["id"]),
            quarantined=result.quarantined or not result.ok,
        )
        row = {
            "run_date": run_date,
            "question_id": question["question_id"],
            "sample_idx": item["sample_idx"],
            "track": item.get("track", "closed_book"),
            "arm": item.get("arm"),
            "attempt": attempt,
            "category": question.get("category"),
            "difficulty": question.get("difficulty"),
            "role": model.get("role"),
            "config_hash": config.config_hash(),
            **result.to_dict(),
            **grade.to_dict(),
        }
        with lock:
            cost += result.cost_usd or 0.0
            if not result.ok:
                failed += 1
            elif result.quarantined:
                quarantined += 1
            else:
                ok += 1
            raw_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            raw_fh.flush()
            if scored_fh is not None:
                scored_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                scored_fh.flush()
            done = ok + failed + quarantined
            if done % 25 == 0 or done == len(plan):
                print(f"  {done}/{len(plan)}  ok={ok} fail={failed} "
                      f"quar={quarantined} ${cost:.2f}", flush=True)
            if cost >= spend_cap:
                aborted["flag"] = True
                aborted["reason"] = aborted["reason"] or f"spend cap ${spend_cap:.2f} reached"
            if out_of_credits(result):
                aborted["flag"] = True
                aborted["reason"] = "OpenRouter credits exhausted (402)"
            elif not result.ok:
                retry_queue.append(item)
        return result

    retry_queue: list[dict[str, Any]] = []

    try:
        with gzip.open(raw_path, "at" if append else "wt", encoding="utf-8") as raw_fh:
            workers = max(1, concurrency)
            if workers == 1:
                for item in plan:
                    one(item)
                    if aborted["flag"]:
                        print(f"{aborted['reason']}; aborting", flush=True)
                        break
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(one, item) for item in plan]
                    for future in as_completed(futures):
                        future.result()
                if aborted["flag"]:
                    print(f"{aborted['reason']}; aborting", flush=True)

            # One retry, for transport failures only (ok=False: timeouts,
            # dropped connections). A substitution quarantine is ok=True and is
            # never retried - it is a finding about routing, and re-sending until
            # the right model answers would erase it. Exactly once, so a dead
            # endpoint cannot loop, and still under the same spend cap.
            first_failures = list(retry_queue)
            retry_queue.clear()
            retried = 0
            if first_failures and not aborted["flag"]:
                print(f"retrying {len(first_failures)} failed call(s) once",
                      flush=True)
                for item in first_failures:
                    if one(item, attempt=attempts.get(_item_key(item), 1) + 1) is None:
                        break
                    retried += 1
            # Anything the cap stopped us retrying is still failed, as is
            # anything that failed its second attempt (left in retry_queue).
            still_failed = len(retry_queue) + (len(first_failures) - retried)
            recovered = retried - len(retry_queue)
    finally:
        if scored_fh is not None:
            scored_fh.close()

    print(f"done ok={ok} fail={failed} quar={quarantined} ${cost:.2f}")
    print(f"retried={retried} recovered={recovered} "
          f"still_failed={still_failed}")
    if aborted["reason"]:
        print(f"ABORTED: {aborted['reason']}. Continue with: "
              f"--resume {raw_path.name.split('.')[0]}")
    print(f"raw {raw_path}")
    return 0 if still_failed == 0 and not aborted["reason"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finbench-run")
    ap.add_argument("--limit", type=int, default=None,
                    help="stratified sample of N questions (pilot: 25)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--models", default=None,
                    help="comma-separated model ids")
    ap.add_argument("--no-reference", action="store_true",
                    help="drop the Perplexity retrieval line")
    ap.add_argument("--spend-cap", type=float,
                    default=float(os.environ.get("FINBENCH_SPEND_CAP", "80")))
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--questions", default=None)
    ap.add_argument("--resume", default=None, metavar="RUN_ID",
                    help="continue an interrupted run: re-plan with the same "
                         "args, skip cells already answered, append to its files")
    ap.add_argument("--track", choices=("closed_book", "reasoning_toggle"),
                    default="closed_book",
                    help="reasoning_toggle calls only the reasoning-ON arm; "
                         "the OFF arm is the main run's own rows")
    args = ap.parse_args(argv)

    config.load_dotenv()
    cfg = config.models()
    qpath = pathlib.Path(args.questions) if args.questions else (
        config.DATA_DIR / "questions.jsonl")
    if not qpath.exists():
        print(f"no questions at {qpath}; run scripts/build_questions.py first",
              file=sys.stderr)
        return 1

    from .gold import read as read_jsonl
    questions = read_jsonl(qpath)
    models = roster(cfg, include_reference=not args.no_reference)
    model_ids = [m.strip() for m in args.models.split(",")] if args.models else None
    samples = args.samples if args.samples is not None else cfg["sampling"]["samples_per_question"]
    if args.track == "reasoning_toggle":
        plan = build_toggle_plan(questions, cfg, samples=args.samples)
        if args.limit is not None:
            plan = plan[:args.limit]  # probe only; never a real toggle run
    else:
        plan = build_plan(questions, models, samples=samples, limit=args.limit,
                          model_ids=model_ids, seed=args.seed)

    attempts: dict[tuple, int] = {}
    if args.resume:
        run_id = args.resume
        prior_path = RAW_DIR / f"{run_id}.jsonl.gz"
        if not prior_path.exists():
            print(f"no raw file for run {run_id}", file=sys.stderr)
            return 1
        with gzip.open(prior_path, "rt", encoding="utf-8") as fh:
            prior = [json.loads(line) for line in fh if line.strip()]
        hashes = {r.get("config_hash") for r in prior}
        if hashes != {config.config_hash()}:
            print(f"refusing to resume: run {run_id} used config {hashes}, "
                  f"current is {config.config_hash()}", file=sys.stderr)
            return 1
        planned = len(plan)
        plan, attempts = resume_plan(plan, prior)
        print(f"resume {run_id}: {planned - len(plan)} of {planned} cells "
              f"already answered, {len(plan)} to go")
    else:
        started = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = hashlib.sha256(
            f"{started}|{config.config_hash()}|{len(plan)}".encode()
        ).hexdigest()[:12]
    print(f"run {run_id}  config_hash={config.config_hash()}")

    cutoffs = load_cutoffs()
    if args.dry_run:
        return execute(plan, client=None, raw_path=None, spend_cap=args.spend_cap,
                       dry_run=True, cutoffs=cutoffs)

    raw_path = RAW_DIR / f"{run_id}.jsonl.gz"
    scored_path = SCORED_DIR / f"{run_id}.jsonl"
    with OpenRouterClient(timeout=300.0) as client:
        return execute(
            plan, client=client, raw_path=raw_path, spend_cap=args.spend_cap,
            dry_run=False, cutoffs=cutoffs, defaults=cfg["defaults"],
            scored_path=scored_path, concurrency=args.concurrency,
            append=bool(args.resume), attempts=attempts,
        )


if __name__ == "__main__":
    raise SystemExit(main())
