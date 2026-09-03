"""Resolve the 58 candidate tickers to CIKs once, then never again.

Prints unresolved tickers loudly rather than dropping them: a silently missing
company would quietly shrink the universe.
"""
from __future__ import annotations

import sys

import yaml

from finbench import config, edgar
from finbench.http import SecClient

ROLES = {
    "A": "recast-heavy parent",
    "B": "short-history spin-off",
    "C": "multi-segment reporter",
    "D": "financial (restricted roles)",
    "E": "share-structure complexity",
    "F": "fiscal-calendar trap",
    "G": "leverage / covenant",
    "ALT": "alternate",
}

# Tickers absent from company_tickers.json. SEC lists only CURRENT registrants
# with an active ticker, so an acquired or renamed company vanishes from that
# file while its CIK and its entire filing history remain valid. Resolved once
# via EDGAR full-text search; this is exactly the failure the spec's "pin CIKs,
# never tickers" rule exists to prevent.
OVERRIDES: dict[str, tuple[int, str, str]] = {
    "K":     (55067,   "KELLANOVA",             "acquired by Mars; delisted, history intact"),
    "KLG":   (1959348, "WK Kellogg Co",         "acquired by Ferrero; delisted, history intact"),
    "LBRDA": (1611983, "Liberty Broadband Corp", "merged into Charter; 4 share classes LBRDA/B/K/P"),
    "SATS":  (1415404, "EchoStar CORP",         "ticker changed SATS -> ECHO"),
}

UNIVERSE: list[tuple[str, str]] = [
    *[(t, "A") for t in "GE MMM DHR JNJ K DD BAX FTV EXC LH IBM WDC BDX ELAN CXT HON".split()],
    *[(t, "B") for t in "GEV SOLV VLTO KVUE KLG".split()],
    *[(t, "C") for t in "INTC AMZN DIS CRM CMCSA WBD EMR TXT PSX MCK UNH".split()],
    *[(t, "D") for t in "BRK.B AIG COF TFC".split()],
    *[(t, "E") for t in "GOOGL FOXA NWSA LBRDA".split()],
    *[(t, "F") for t in "NKE ORCL COST DE AVGO".split()],
    *[(t, "G") for t in "CHTR SATS CCL CYH CVNA".split()],
    *[(t, "ALT") for t in "MU CSCO FDX JBL NDSN SYY UAA BHC".split()],
]


def main() -> int:
    config.load_dotenv()
    with SecClient() as client:
        index = edgar.fetch_ticker_index(client)

    resolved, missing, overridden = [], [], []
    for ticker, role in UNIVERSE:
        company = index.get(edgar.normalise_ticker(ticker))
        entry = {"ticker": ticker, "role": role, "role_label": ROLES[role]}
        if company is not None:
            entry |= {"cik": company.cik, "name": company.name}
        elif ticker in OVERRIDES:
            cik, name, note = OVERRIDES[ticker]
            entry |= {"cik": cik, "name": name, "ticker_note": note}
            overridden.append(ticker)
        else:
            missing.append(ticker)
            continue
        resolved.append(entry)

    if overridden:
        print(f"resolved via override ({len(overridden)}): {', '.join(overridden)}")
    if missing:
        print(f"UNRESOLVED ({len(missing)}): {', '.join(missing)}", file=sys.stderr)

    out = config.CONFIG_DIR / "companies.yaml"
    out.write_text(yaml.safe_dump(
        {"version": 1, "companies": resolved}, sort_keys=False, allow_unicode=True))
    print(f"resolved {len(resolved)}/{len(UNIVERSE)} -> {out}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
