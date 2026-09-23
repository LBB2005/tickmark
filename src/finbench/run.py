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
    aborted = {"flag": False}

    scored_fh = None
    if scored_path is not None:
        scored_fh = scored_path.open("w", encoding="utf-8")

    def one(item: dict[str, Any]) -> None:
        nonlocal cost, ok, failed, quarantined
        with lock:
            if aborted["flag"] or cost >= spend_cap:
                aborted["flag"] = True
                return
        model = item["model"]
        question = item["question"]
        result = client.call(
            model=model,
            messages=prompts.build_messages(question),
            temperature=defaults.get("temperature", 0),
            max_tokens=defaults.get("max_tokens", 700),
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
            "track": "closed_book",
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

    try:
        with gzip.open(raw_path, "wt", encoding="utf-8") as raw_fh:
            workers = max(1, concurrency)
            if workers == 1:
                for item in plan:
                    one(item)
                    if aborted["flag"]:
                        print(f"spend cap ${spend_cap:.2f} reached; aborting",
                              flush=True)
                        break
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(one, item) for item in plan]
                    for future in as_completed(futures):
                        future.result()
                if aborted["flag"]:
                    print(f"spend cap ${spend_cap:.2f} reached; aborting",
                          flush=True)
    finally:
        if scored_fh is not None:
            scored_fh.close()

    print(f"done ok={ok} fail={failed} quar={quarantined} ${cost:.2f}")
    print(f"raw {raw_path}")
    return 0 if failed == 0 else 1


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
    plan = build_plan(questions, models, samples=samples, limit=args.limit,
                      model_ids=model_ids, seed=args.seed)

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
        )


if __name__ == "__main__":
    raise SystemExit(main())
