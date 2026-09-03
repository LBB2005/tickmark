"""companyfacts -> flat observation records.

companyfacts returns every fact-observation ever filed, not the current value
of each fact. That is the property the whole restatement track depends on, so
nothing here deduplicates.

Periods are keyed on (start, end), never on (fy, fp): when a company recasts a
prior year, the recast figure is filed under a LATER fy with the SAME calendar
period. Keying on fy would put the original and the recast in different groups
and find zero restatements.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class Obs:
    concept: str
    unit: str
    start: str | None
    end: str
    val: float
    accn: str
    form: str
    filed: str
    fy: int | None
    fp: str | None

    @property
    def period_key(self) -> tuple[str | None, str]:
        return (self.start, self.end)

    @property
    def is_instant(self) -> bool:
        return self.start is None


def iter_observations(facts: dict, taxonomy: str = "us-gaap") -> Iterator[Obs]:
    for concept, body in facts.get("facts", {}).get(taxonomy, {}).items():
        for unit, rows in body.get("units", {}).items():
            for row in rows:
                if "val" not in row or "end" not in row:
                    continue
                yield Obs(
                    concept=concept,
                    unit=unit,
                    start=row.get("start"),
                    end=row["end"],
                    val=row["val"],
                    accn=row.get("accn", ""),
                    form=row.get("form", ""),
                    filed=row.get("filed", ""),
                    fy=row.get("fy"),
                    fp=row.get("fp"),
                )


def public_float(facts: dict) -> float | None:
    """Salience proxy, free from the 10-K cover page.

    Spec section 5.1 wants a market-cap-like continuous variable.
    dei:EntityPublicFloat is already in companyfacts, so this needs no price
    API and no extra dependency.
    """
    values = [o for o in iter_observations(facts, taxonomy="dei")
              if o.concept == "EntityPublicFloat"]
    if not values:
        return None
    return max(values, key=lambda o: o.filed).val
