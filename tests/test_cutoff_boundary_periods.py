"""Period labels on post-cutoff boundary records.

build_cutoff_boundary used to call phrase_for_form(source_form, obs.end),
which ignores the observation's actual duration, so:

* a 3-month comparative whose latest accession is a 10-K was labeled
  "the fiscal year ended ...", and
* a 6- or 9-month YTD fact in a 10-Q was labeled "the three months ended ...".

Found in verification round 1 (DuPont, Honeywell, and 11 records outside the
sample). These pin the label to the observation's own start and end.
"""
from __future__ import annotations

import build_gold as bg


def _facts(start, end, val, accn, form, filed, concept="Revenues"):
    """Minimal companyfacts payload with one duration observation."""
    return {
        "facts": {
            "us-gaap": {
                concept: {
                    "units": {
                        "USD": [{
                            "start": start, "end": end, "val": val,
                            "accn": accn, "fy": int(end[:4]), "fp": "Q1",
                            "form": form, "filed": filed,
                        }]
                    }
                }
            }
        }
    }


def test_quarter_filed_in_10k_is_not_called_a_fiscal_year():
    # DuPont Q1 2024 revenue ($1.599B) lives on the FY2025 10-K accession as a
    # comparative. phrase_for_form sees form=10-K and writes "fiscal year".
    accn = "0001666700-26-000013"
    universe = [{
        "ticker": "DD", "name": "DuPont de Nemours, Inc.",
        "cik": "1666700", "role": "A",
    }]
    facts = {1666700: _facts(
        "2024-01-01", "2024-03-31", 1_599_000_000, accn, "10-K", "2026-02-17",
        concept="RevenueFromContractWithCustomerExcludingAssessedTax",
    )}
    submissions = {1666700: [("10-K", "2025-12-31", "2026-02-17", accn)]}

    records = bg.build_cutoff_boundary(universe, facts, submissions)

    assert records, "expected a boundary record from the Q1 observation"
    assert records[0]["gold_value"] == 1_599_000_000
    assert records[0]["fiscal_period"] == "the three months ended March 31, 2024"


def test_ytd_fact_in_10q_is_labeled_by_duration_not_form():
    # Nike 9-month YTD revenue ($38.756B) in a 10-Q is currently labeled
    # "three months" because phrase_for_form only looks at the form type.
    accn = "0000320187-25-000016"
    universe = [{
        "ticker": "NKE", "name": "NIKE, Inc.",
        "cik": "320187", "role": "F",
    }]
    facts = {320187: _facts(
        "2023-06-01", "2024-02-29", 38_756_000_000, accn, "10-Q", "2025-04-03",
    )}
    submissions = {320187: [("10-Q", "2024-02-29", "2025-04-03", accn)]}

    records = bg.build_cutoff_boundary(universe, facts, submissions)

    assert records, "expected a boundary record from the YTD observation"
    assert records[0]["gold_value"] == 38_756_000_000
    assert records[0]["fiscal_period"] == "the nine months ended February 29, 2024"
