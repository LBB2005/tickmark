"""Freeze gold records into questions.jsonl (spec section 6.6).

Run after gold is stable. Broken questions found later are excluded and
reported, never edited in place.
"""
from __future__ import annotations

from finbench import config, gold, questions


def main() -> int:
    records = gold.read(config.DATA_DIR / "gold.jsonl")
    path = config.DATA_DIR / "questions.jsonl"
    digest_path = config.DATA_DIR / "QUESTIONS.sha256"
    n, digest = questions.freeze(records, path, digest_path)
    print(f"{n} questions -> {path}")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
