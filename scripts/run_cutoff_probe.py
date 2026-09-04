"""Ask every model in the roster what its knowledge cutoff is (spec 7.4).

Sampled more than once on purpose. Gemini answered 2025-01 and then 2024-08 to
identical calls at temperature 0, so a single sample would have recorded a
confident-looking boundary that the model does not actually hold. Disagreement
across samples is a finding in its own right: a model that cannot state its own
cutoff consistently cannot reliably know when to abstain.
"""
from __future__ import annotations

import collections
import datetime as dt
import json

from finbench import config, probe_cutoff
from finbench.clients import OpenRouterClient

SAMPLES = 3


def main() -> int:
    config.load_dotenv()
    cfg = config.models()
    roster = list(cfg["models"]) + list(cfg.get("reference_line", []))
    out = config.DATA_DIR / "cutoff_probe.jsonl"
    run_date = dt.datetime.now(dt.timezone.utc).isoformat()

    rows, total_cost = [], 0.0
    with OpenRouterClient(timeout=300.0) as client:
        for model in roster:
            answers, samples = [], []
            for index in range(SAMPLES):
                result = client.call(model=model, prompt=probe_cutoff.PROMPT,
                                     temperature=0.0, max_tokens=4000)
                total_cost += result.cost_usd or 0.0
                stated = probe_cutoff.parse_cutoff(result.text)
                if result.ok and not result.quarantined:
                    answers.append(stated)
                samples.append({
                    "sample_idx": index, "stated_cutoff": stated,
                    "raw_text": result.text, "ok": result.ok,
                    "quarantined": result.quarantined,
                    "quarantine_reason": result.quarantine_reason,
                    "resolved_model": result.resolved_model,
                    "resolved_provider": result.resolved_provider,
                    "cost_usd": result.cost_usd, "error": result.error,
                })

            usable = [a for a in answers if a]
            counts = collections.Counter(usable)
            modal = counts.most_common(1)[0][0] if counts else None
            stable = len(set(usable)) <= 1 and bool(usable)
            flag = "" if stable else f"  UNSTABLE {sorted(set(usable))}"
            print(f"  {model['id']:<16} {str(modal):<9} "
                  f"{len(usable)}/{SAMPLES} usable{flag}")
            rows.append({"model_id": model["id"], "slug": model["slug"],
                         "run_date": run_date, "stated_cutoff": modal,
                         "stable": stable, "distinct_answers": sorted(set(usable)),
                         "samples": samples})

    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    unstable = [r["model_id"] for r in rows if not r["stable"]]
    print(f"\n{len(rows)} models probed -> {out}   cost ${total_cost:.4f}")
    if unstable:
        print(f"UNSTABLE stated cutoff: {', '.join(unstable)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
