"""Headline metrics from scored rows (spec section 9).

Accuracy is the control. Calibration — confident-wrong, ECE, Brier,
confidence AUC — is the finding. Every rate carries a Wilson interval.
"""
from __future__ import annotations

import json
import pathlib
from collections import defaultdict
from typing import Any

from . import stats

CONFIDENT_THRESHOLDS = (50, 75, 90)
# Outcomes in which the model gave an answer and it was wrong - the same set
# scoring.grade can mark confident_wrong.
ANSWERED_WRONG = {"wrong", "scale_error", "fabricated", "leaked_post_cutoff"}
BEHAVIORAL_MIN = 75
BEHAVIORAL_WRONG = 3
BEHAVIORAL_CORRECT = 1


def _usable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows
            if not r.get("quarantined") and r.get("outcome") != "quarantined"
            and r.get("correct") is not None]


def _rate(k: int, n: int) -> dict[str, Any]:
    if n <= 0:
        return {"k": 0, "n": 0, "point": None, "low": None, "high": None}
    interval = stats.wilson(k, n)
    return {"k": k, "n": n, "point": interval.point,
            "low": interval.low, "high": interval.high}


def _brier(rows: list[dict[str, Any]]) -> float | None:
    pairs = []
    for row in rows:
        if row.get("confidence") is None or row.get("correct") is None:
            continue
        pairs.append(((row["confidence"] / 100.0) - float(row["correct"])) ** 2)
    if not pairs:
        return None
    return sum(pairs) / len(pairs)


def _ece(rows: list[dict[str, Any]], n_bins: int = 10) -> float | None:
    pairs = [(r["confidence"], float(r["correct"]))
             for r in rows
             if r.get("confidence") is not None and r.get("correct") is not None]
    if not pairs:
        return None
    bins: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    width = 100 / n_bins
    for confidence, y in pairs:
        index = min(n_bins - 1, int(confidence / width))
        bins[index].append((confidence / 100.0, y))
    total = len(pairs)
    error = 0.0
    for bucket in bins:
        if not bucket:
            continue
        mean_p = sum(p for p, _ in bucket) / len(bucket)
        mean_y = sum(y for _, y in bucket) / len(bucket)
        error += (len(bucket) / total) * abs(mean_p - mean_y)
    return error


def confidence_auc(rows: list[dict[str, Any]]) -> float | None:
    """P(correct row has higher confidence than an incorrect one)."""
    correct = [r["confidence"] for r in rows
               if r.get("correct") is True and r.get("confidence") is not None]
    wrong = [r["confidence"] for r in rows
             if r.get("correct") is False and r.get("confidence") is not None]
    if not correct or not wrong:
        return None
    wins = ties = 0
    for c in correct:
        for w in wrong:
            if c > w:
                wins += 1
            elif c == w:
                ties += 1
    return (wins + 0.5 * ties) / (len(correct) * len(wrong))


def _behavioral(rows: list[dict[str, Any]]) -> float | None:
    """Answer only above the threshold: +1 correct, 0 abstain, -3 wrong."""
    if not rows:
        return None
    score = 0.0
    for row in rows:
        conf = row.get("confidence")
        if conf is None or conf < BEHAVIORAL_MIN:
            continue
        if row.get("correct") is True:
            score += BEHAVIORAL_CORRECT
        elif row.get("correct") is False:
            score -= BEHAVIORAL_WRONG
    return score / len(rows)


def _by_field(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field) or "none")].append(row)
    out = {}
    for key, group in sorted(groups.items()):
        k = sum(1 for r in group if r.get("correct") is True)
        out[key] = _rate(k, len(group))
    return out


def _track(row: dict[str, Any]) -> str:
    return row.get("track") or "closed_book"


def _cell(row: dict[str, Any]) -> tuple:
    return (row["question_id"], row["model_id"], row.get("sample_idx"),
            _track(row), row.get("arm"))


def _dedup(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """One row per (question, model, sample, track, arm) cell.

    A transport failure retried once leaves two rows for the same cell. The
    successful attempt is the measurement; the failed one is kept in raw as
    the audit trail but must not count twice, and must not count as a
    quarantine either - a timeout that later succeeded is not a finding.
    A cell that never succeeded is kept as still_failed, never dropped quietly.
    """
    cells: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cells[_cell(row)].append(row)
    kept: list[dict[str, Any]] = []
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"retried": 0, "still_failed": 0})
    for key, group in cells.items():
        group = sorted(group, key=lambda r: r.get("attempt") or 1)
        succeeded = [r for r in group if r.get("ok") is not False]
        chosen = succeeded[-1] if succeeded else group[-1]
        # Only a transport failure makes a retry. A 402 is the account running
        # dry; the cell re-run on --resume was never retried in that sense.
        if any(r.get("ok") is False and not str(r.get("error") or "").startswith("402")
               for r in group[:-1]):
            counts[key[1]]["retried"] += 1
        if not succeeded:
            counts[key[1]]["still_failed"] += 1
        kept.append(chosen)
    return kept, counts


def _model_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = _usable(rows)
    cw = sum(1 for r in usable if r.get("confident_wrong"))
    fp = [r for r in usable if r.get("bucket") == "false_premise"
          or r.get("category") == "false_premise"]
    fabricated = sum(1 for r in fp if r.get("outcome") == "fabricated")
    numeric = [r for r in usable if r.get("bucket") == "numeric"]
    numeric_correct = sum(1 for r in numeric if r.get("correct") is True)
    must_hold = [r for r in usable if r.get("bucket") == "must_abstain"]
    held = sum(1 for r in must_hold if r.get("outcome") == "abstained")
    format_ok = sum(1 for r in usable if r.get("format_ok"))
    false_refusals = sum(1 for r in numeric if r.get("outcome") == "false_refusal")
    return {
        "n": len(usable),
        "quarantined": sum(1 for r in rows if r.get("ok") is not False
                           and (r.get("quarantined")
                                or r.get("outcome") == "quarantined")),
        "confident_wrong": _rate(cw, len(usable)),
        "numeric_accuracy": _rate(numeric_correct, len(numeric)),
        "fabrication": _rate(fabricated, len(fp)),
        "post_cutoff_abstention": _rate(held, len(must_hold)),
        "false_refusal": _rate(false_refusals, len(numeric)),
        "format_ok": _rate(format_ok, len(usable)),
        "by_category": _by_field(usable, "category"),
        "by_difficulty": _by_field(
            [r for r in usable if r.get("difficulty")], "difficulty"),
        "ece": _ece(usable),
        "brier": _brier(usable),
        "confidence_auc": confidence_auc(usable),
        "behavioral": _behavioral(usable),
        # Only outcomes where the model committed to an answer. `correct is
        # False` also covers false refusals, and an abstention at confidence
        # 100 is a model sure that declining is right, not a confident error;
        # counting it made Gemini read 29.2% at >=90 against a 0.2% headline.
        # At the frozen threshold this reproduces the headline exactly.
        "confident_wrong_at": {
            str(t): _rate(sum(1 for r in usable
                              if r.get("outcome") in ANSWERED_WRONG
                              and r.get("confidence") is not None
                              and r["confidence"] >= t),
                          len(usable))
            for t in CONFIDENT_THRESHOLDS
        },
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # The headline is closed-book only. Toggle rows reuse a main-run model id,
    # so without this filter they would silently fold into that model's rates.
    main, counts = _dedup([r for r in rows if _track(r) == "closed_book"])
    by_model: dict[str, list] = defaultdict(list)
    for row in main:
        by_model[row["model_id"]].append(row)
    models = {}
    for mid, group in sorted(by_model.items()):
        block = _model_summary(group)
        block.update(counts.get(mid, {"retried": 0, "still_failed": 0}))
        models[mid] = block
    toggle_models = sorted({r["model_id"] for r in rows
                            if _track(r) == "reasoning_toggle"})
    return {
        "n_rows": len(rows),
        "models": models,
        "toggle": (summarise_toggle(rows, model_id=toggle_models[0])
                   if toggle_models else None),
    }


def summarise_toggle(rows: list[dict[str, Any]], *, model_id: str) -> dict[str, Any] | None:
    """Spec 7.7: the same model and cells, reasoning on vs off.

    The OFF arm is the main run's rows for exactly the cells the ON arm
    covered, so both arms answer identical (question, sample) pairs on the same
    run date. Everything else about the main run is excluded.
    """
    on, _ = _dedup([r for r in rows if _track(r) == "reasoning_toggle"
                    and r["model_id"] == model_id])
    if not on:
        return None
    wanted = {(r["question_id"], r.get("sample_idx")) for r in on}
    off, _ = _dedup([r for r in rows if _track(r) == "closed_book"
                     and r["model_id"] == model_id
                     and (r["question_id"], r.get("sample_idx")) in wanted])

    def arm(group):
        block = _model_summary(group)
        usable = _usable(group)
        block["abstention"] = _rate(
            sum(1 for r in usable if r.get("outcome") == "abstained"), len(usable))
        return block

    off_by = {(r["question_id"], r.get("sample_idx")): r for r in _usable(off)}
    on_by = {(r["question_id"], r.get("sample_idx")): r for r in _usable(on)}
    paired = sorted(set(off_by) & set(on_by))
    flips = {"wrong_to_right": 0, "right_to_wrong": 0}
    for key in paired:
        before, after = off_by[key].get("correct"), on_by[key].get("correct")
        if before is False and after is True:
            flips["wrong_to_right"] += 1
        elif before is True and after is False:
            flips["right_to_wrong"] += 1
    return {
        "model_id": model_id,
        "questions": len({q for q, _ in wanted}),
        "paired_cells": len(paired),
        "off": arm(off),
        "on": arm(on),
        "flips": flips,
    }


def _pct(rate: dict[str, Any]) -> str:
    if not rate or rate.get("point") is None:
        return "n/a"
    return (f"{100 * rate['point']:.1f}% "
            f"({rate['k']}/{rate['n']}; "
            f"{100 * rate['low']:.1f}–{100 * rate['high']:.1f})")


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Tickmark closed-book results",
        "",
        "Intervals are Wilson 90%. Confident-wrong is the headline; "
        "numeric accuracy is the control.",
        "",
        "| Model | n | Confident-wrong | Numeric accuracy | Fabrication | Format |",
        "|---|---:|---|---|---|---|",
    ]
    for model_id, block in summary["models"].items():
        lines.append(
            f"| {model_id} | {block['n']} | "
            f"{_pct(block['confident_wrong'])} | "
            f"{_pct(block['numeric_accuracy'])} | "
            f"{_pct(block['fabrication'])} | "
            f"{_pct(block['format_ok'])} |"
        )
    lines += ["", "## Calibration", ""]
    for model_id, block in summary["models"].items():
        auc = block["confidence_auc"]
        lines.append(
            f"- **{model_id}**: ECE {None if block['ece'] is None else round(block['ece'], 3)}, "
            f"Brier {None if block['brier'] is None else round(block['brier'], 3)}, "
            f"confidence AUC {None if auc is None else round(auc, 3)}, "
            f"behavioral {None if block['behavioral'] is None else round(block['behavioral'], 3)}"
        )
    lines += ["", "## Coverage", ""]
    for model_id, block in summary["models"].items():
        lines.append(
            f"- **{model_id}**: {block['n']} scored, "
            f"{block.get('retried', 0)} retried once, "
            f"{block.get('still_failed', 0)} still failed, "
            f"{block.get('quarantined', 0)} quarantined (substitution)"
        )
    toggle = summary.get("toggle")
    if toggle:
        lines += [
            "", f"## Reasoning toggle ({toggle['model_id']})", "",
            f"{toggle['questions']} questions, {toggle['paired_cells']} paired "
            "(question, sample) cells per arm. The off arm is the main run's own "
            "rows for these cells. Small n: directional only.",
            "",
            "| Arm | n | Confident-wrong | Numeric accuracy | Abstention | ECE |",
            "|---|---:|---|---|---|---|",
        ]
        for name in ("off", "on"):
            b = toggle[name]
            lines.append(
                f"| reasoning {name} | {b['n']} | {_pct(b['confident_wrong'])} | "
                f"{_pct(b['numeric_accuracy'])} | {_pct(b['abstention'])} | "
                f"{None if b['ece'] is None else round(b['ece'], 3)} |")
        f = toggle["flips"]
        lines += ["", f"Paired flips: {f['wrong_to_right']} wrong→right, "
                      f"{f['right_to_wrong']} right→wrong."]
    return "\n".join(lines) + "\n"


def write_outputs(summary: dict[str, Any], directory: pathlib.Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n")
    # Generated tables only. results/REPORT.md is the hand-written report and
    # must survive a re-analysis, so this never writes to it.
    (directory / "TABLES.md").write_text(render_report(summary))


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows = []
    opener = path.open
    if path.suffix == ".gz" or path.name.endswith(".jsonl.gz"):
        import gzip
        opener = lambda: gzip.open(path, "rt", encoding="utf-8")  # noqa: E731
    with opener() as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows
