"""Restatement detection by groupby.

group by (concept, unit, period) -> if more than one distinct value survives
the material-change filter, the later-filed value supersedes the earlier one.
The model almost certainly absorbed the ORIGINAL figure during training, which
is what makes these the hardest questions in the set.

Two filters keep this honest:
  * a minimum relative change, so rounding revisions are not called
    restatements;
  * different accessions, so two copies of the same filing are not either.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .observations import Obs, iter_observations

SCORED_FORMS = ("10-K", "10-Q", "10-K/A", "10-Q/A")
MIN_RELATIVE_CHANGE = 0.005
SCALE_TOLERANCE = 0.01  # how close to an exact power of 1000 counts as a retag

# Concepts an analyst would actually ask about. Spec section 6.2 requires the
# prompt to name the concept the way an analyst would ("revenue", not
# RevenueFromContractWithCustomerExcludingAssessedTax) - which is impossible
# for tags like IncomeTaxHolidayIncomeTaxBenefitsPerShare. Restricting to this
# list takes GE from 3,361 raw hits to a set that can be phrased as questions.
HEADLINE_CONCEPTS: frozenset[str] = frozenset({
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "GrossProfit",
    "OperatingIncomeLoss",
    "ResearchAndDevelopmentExpense",
    "SellingGeneralAndAdministrativeExpense",
    "NetIncomeLoss",
    "ProfitLoss",
    "ComprehensiveIncomeNetOfTax",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
    "Assets",
    "AssetsCurrent",
    "Liabilities",
    "LiabilitiesCurrent",
    "StockholdersEquity",
    "Goodwill",
    "InventoryNet",
    "PropertyPlantAndEquipmentNet",
    "CashAndCashEquivalentsAtCarryingValue",
    "LongTermDebtNoncurrent",
    "LongTermDebt",
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInInvestingActivities",
    "NetCashProvidedByUsedInFinancingActivities",
    "IncomeTaxExpenseBenefit",
})


def _is_scale_artifact(a: float, b: float, tolerance: float = SCALE_TOLERANCE) -> bool:
    """True when b is a is rescaled by a power of 1000 (a thousands->units retag).

    3M filed WeightedAverage... as 34,965 then as 34,965,000. That is the same
    number in different units, not a revision, and it would generate a question
    whose "correct" answer depends on which filing you happened to read.
    """
    if a == 0 or b == 0:
        return False
    ratio = abs(b) / abs(a)
    for power in (1e-9, 1e-6, 1e-3, 1e3, 1e6, 1e9):
        if abs(ratio - power) <= tolerance * power:
            return True
    return False


@dataclass(frozen=True)
class Restatement:
    concept: str
    unit: str
    start: str | None
    end: str
    gold_value: float
    superseded_value: float
    source_accn: str
    source_form: str
    source_filed: str
    superseded_accn: str
    superseded_filed: str
    relative_change: float


def _group(facts: dict, forms: tuple[str, ...]) -> dict[tuple, list[Obs]]:
    groups: dict[tuple, list[Obs]] = defaultdict(list)
    for obs in iter_observations(facts):
        if obs.form not in forms:
            continue
        groups[(obs.concept, obs.unit, obs.start, obs.end)].append(obs)
    return groups


def find(
    facts: dict,
    *,
    min_relative_change: float = MIN_RELATIVE_CHANGE,
    forms: tuple[str, ...] = SCORED_FORMS,
    concepts: frozenset[str] | None = HEADLINE_CONCEPTS,
) -> list[Restatement]:
    """Find restated figures. Pass concepts=None to see every tag unfiltered."""
    out: list[Restatement] = []
    for (concept, unit, start, end), observations in _group(facts, forms).items():
        if concepts is not None and concept not in concepts:
            continue
        if len({o.val for o in observations}) < 2:
            continue
        observations.sort(key=lambda o: (o.filed, o.accn))
        original, latest = observations[0], observations[-1]
        if original.accn == latest.accn or original.val == latest.val:
            continue
        # A concept that was absent-as-zero and later tagged is not a revision,
        # and its relative change is meaningless (GE: 0 -> 213bn = 2e13%).
        if original.val == 0 or latest.val == 0:
            continue
        if _is_scale_artifact(original.val, latest.val):
            continue
        change = abs(latest.val - original.val) / abs(original.val)
        if change < min_relative_change:
            continue
        out.append(Restatement(
            concept=concept, unit=unit, start=start, end=end,
            gold_value=latest.val, superseded_value=original.val,
            source_accn=latest.accn, source_form=latest.form,
            source_filed=latest.filed,
            superseded_accn=original.accn, superseded_filed=original.filed,
            relative_change=change,
        ))
    out.sort(key=lambda r: r.relative_change, reverse=True)
    return out
