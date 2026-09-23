"""Run the closed-book eval. Thin wrapper around `python -m finbench.run`."""
from finbench.run import main

if __name__ == "__main__":
    raise SystemExit(main())
