"""Score a raw run into results/summary.json and results/REPORT.md."""
from __future__ import annotations

import argparse
import pathlib
import sys

from finbench import analyze, config


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finbench-analyze")
    ap.add_argument("path", help="scored jsonl or gzipped raw jsonl")
    ap.add_argument("--out", default=None, help="output directory (default results/)")
    args = ap.parse_args(argv)

    path = pathlib.Path(args.path)
    if not path.exists():
        print(f"no file at {path}", file=sys.stderr)
        return 1
    rows = analyze.read_jsonl(path)
    summary = analyze.summarise(rows)
    out = pathlib.Path(args.out) if args.out else (config.ROOT / "results")
    analyze.write_outputs(summary, out)
    print(analyze.render_report(summary))
    print(f"wrote {out / 'summary.json'} and {out / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
