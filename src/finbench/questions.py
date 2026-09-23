"""Render gold records into the frozen question set (spec section 6).

Every question is generated from a fact already held. The rendered text is
part of the measurement instrument, so it is written to questions.jsonl and
hashed: later edits are exclusions, never silent rewrites.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any, Iterable

from . import prompts


def render(record: dict[str, Any]) -> dict[str, Any]:
    """Attach the analyst-facing question to a copy of the gold record."""
    ticker = prompts.ticker_for(record["cik"])
    frozen = dict(record)
    frozen["question"] = prompts.question_text(record, ticker)
    return frozen


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(
    records: Iterable[dict[str, Any]],
    path: pathlib.Path,
    digest_path: pathlib.Path | None = None,
) -> tuple[int, str]:
    """Write rendered questions and the matching sha256 sidecar."""
    rows = [render(record) for record in records]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    digest = sha256_file(path)
    if digest_path is not None:
        digest_path.write_text(f"{digest}  {path.name}\n")
    return len(rows), digest
