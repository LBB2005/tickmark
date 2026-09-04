"""Pick the model roster from OpenRouter's live catalogue (spec section 7.3).

Never hardcode slugs from memory: labs ship, rename and retire models, and a
roster invented from training data is the fastest way to an irreproducible
result. This hits GET /api/v1/models and prints what actually exists today,
with per-token pricing, so the choices can be pinned in config/models.yaml.

Slot 5 needs a cheap model from the SAME generation as one of the flagships
(spec section 7.1). A cross-generation pair confounds model size with vintage,
which would make the tier comparison unreadable.
"""
from __future__ import annotations

import os
import sys

import httpx

from finbench import config

API = "https://openrouter.ai/api/v1/models"

LABS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "x-ai": "xAI",
    "perplexity": "Perplexity",
}


def price_per_mtok(model: dict, key: str) -> float | None:
    raw = (model.get("pricing") or {}).get(key)
    try:
        return float(raw) * 1_000_000
    except (TypeError, ValueError):
        return None


def main() -> int:
    config.load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    response = httpx.get(API, headers=headers, timeout=60.0)
    if response.status_code != 200:
        print(f"FAILED {response.status_code}: {response.text[:300]}", file=sys.stderr)
        return 1
    models = response.json().get("data", [])
    print(f"key present: {bool(key)}   models in catalogue: {len(models)}\n")

    for prefix, label in LABS.items():
        rows = [m for m in models if m["id"].startswith(f"{prefix}/")]
        rows = [m for m in rows if not any(
            s in m["id"] for s in (":free", "-online", ":thinking", ":extended"))]
        priced = []
        for m in rows:
            inp, out = price_per_mtok(m, "prompt"), price_per_mtok(m, "completion")
            if inp is None or out is None or inp == 0:
                continue
            priced.append((inp, out, m))
        priced.sort(key=lambda r: -r[0])
        print(f"=== {label} ({len(priced)} priced) ===")
        for inp, out, m in priced[:6]:
            ctx = m.get("context_length") or 0
            print(f"  {m['id']:<44} in=${inp:>7.2f} out=${out:>7.2f} /Mtok  ctx={ctx:>9,}")
        if len(priced) > 6:
            cheap = priced[-3:]
            print("  ... cheapest:")
            for inp, out, m in cheap:
                print(f"  {m['id']:<44} in=${inp:>7.2f} out=${out:>7.2f} /Mtok")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
