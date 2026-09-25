"""Score a run into results/summary.json and results/TABLES.md.

results/REPORT.md is written by hand from these and is never overwritten.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from finbench import analyze, config


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finbench-analyze")
    ap.add_argument("paths", nargs="+",
                    help="scored jsonl or gzipped raw jsonl; pass the main run "
                         "and the reasoning-toggle run together")
    ap.add_argument("--out", default=None, help="output directory (default results/)")
    args = ap.parse_args(argv)

    rows = []
    for raw in args.paths:
        path = pathlib.Path(raw)
        if not path.exists():
            print(f"no file at {path}", file=sys.stderr)
            return 1
        rows.extend(analyze.read_jsonl(path))
    summary = analyze.summarise(rows)
    out = pathlib.Path(args.out) if args.out else (config.ROOT / "results")
    analyze.write_outputs(summary, out)
    print(analyze.render_report(summary))
    print(f"wrote {out / 'summary.json'} and {out / 'TABLES.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
