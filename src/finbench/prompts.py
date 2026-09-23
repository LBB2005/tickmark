"""Closed-book question rendering (spec section 7.1).

The rendered question is the measurement instrument, so two properties are
enforced by tests rather than by care. A false-premise question is rendered
through exactly the same template as a real segment question, and a
post-cutoff question through the same template as an answerable one. If the
category were legible from the wording, the benchmark would measure trap
detection instead of parametric recall.

Company names are the EDGAR registrant strings verbatim, with the ticker
appended. They read oddly ("DANAHER CORP /DE/"), but title-casing them is a
transformation this project cannot verify, and ambiguity about which
registrant is being asked costs more than typography.
"""
from __future__ import annotations

import functools
import json
import re
from typing import Any

from . import config

# XBRL tags never reach the model. An unmapped tag raises rather than leaking
# a raw concept name into a question a human analyst would never type.
CONCEPT_PHRASES = {
    "Revenues": "total revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax":
        "revenue from contracts with customers",
    "RevenueFromContractWithCustomerIncludingAssessedTax":
        "revenue from contracts with customers, including assessed taxes",
    "CostOfRevenue": "cost of revenue",
    "CostOfGoodsAndServicesSold": "cost of goods and services sold",
    "OperatingIncomeLoss": "operating income",
    "NetIncomeLoss": "net income",
    "ComprehensiveIncomeNetOfTax": "comprehensive income, net of tax",
    "IncomeTaxExpenseBenefit": "income tax expense",
    "ResearchAndDevelopmentExpense": "research and development expense",
    "SellingGeneralAndAdministrativeExpense":
        "selling, general and administrative expense",
    "NetCashProvidedByUsedInOperatingActivities":
        "net cash provided by operating activities",
    "NetCashProvidedByUsedInInvestingActivities":
        "net cash used in investing activities",
    "NetCashProvidedByUsedInFinancingActivities":
        "net cash used in financing activities",
    "EarningsPerShareBasic": "basic earnings per share",
    "EarningsPerShareDiluted": "diluted earnings per share",
    "EntityCommonStockSharesOutstanding": None,  # rendered as a count, below
}

_SEGMENT_SUFFIX = re.compile(
    r"\s*(reportable\s+segment|operating\s+segment|segment|member)\s*$",
    re.IGNORECASE,
)

RESPONSE_SCHEMA_EXAMPLE = json.dumps(
    {
        "answer": 12345678900,
        "unit": "USD",
        "confidence": 70,
        "abstain": False,
        "note": "",
    },
    indent=2,
)

SYSTEM = (
    "You are answering from memory, closed-book. You have no filings, no "
    "retrieval and no browsing available, and you must not pretend otherwise. "
    "Reply with a single JSON object and nothing else - no prose before it, no "
    "code fence around it."
)

_INSTRUCTIONS = f"""Answer with a single JSON object in exactly this shape:

{RESPONSE_SCHEMA_EXAMPLE}

  answer      the figure, as a plain number with no separators or units, or
              null if you are abstaining.
  unit        the unit the figure is in, for example "USD", "USD/shares" or
              "shares".
  confidence  an integer from 0 to 100: your probability that the answer is
              correct as stated.
  abstain     true if you are declining to give a figure. Set answer to null
              when this is true.
  note        at most two sentences. Say anything about the question itself
              that the figure alone does not capture. Leave it empty if there
              is nothing to say."""


@functools.cache
def _tickers() -> dict[int, str]:
    return {
        entry["cik"]: entry["ticker"]
        for entry in config.companies()["companies"]
    }


def ticker_for(cik: int) -> str | None:
    return _tickers().get(cik)


def display_company(record: dict[str, Any], ticker: str | None) -> str:
    name = record["company"]
    return f"{name} ({ticker})" if ticker else name


def _segment_phrase(record: dict[str, Any]) -> str:
    label = record.get("segment_label") or record.get("nonexistent_segment")
    if not label:
        return ""
    if record.get("segment_axis") == "Geographical":
        return f" in {label}"
    bare = _SEGMENT_SUFFIX.sub("", label).strip()
    if not bare:
        raise ValueError(f"segment label is only boilerplate: {label!r}")
    return f" in the {bare} segment"


def question_text(record: dict[str, Any], ticker: str | None = None) -> str:
    """Render one gold record as the question an analyst would type."""
    concept = record["concept"]
    if concept not in CONCEPT_PHRASES:
        raise KeyError(f"no question phrasing for concept {concept!r}")

    company = display_company(record, ticker)
    period = record["fiscal_period"]
    restated = record.get("category") == "restatement"

    if concept == "EntityCommonStockSharesOutstanding":
        body = (
            f"how many shares of common stock did {company} have outstanding "
            f"{period}?"
        )
        if restated:
            # Same load-bearing phrase as the numeric restatement template:
            # the superseded figure is what the model almost certainly memorised.
            return f"As most recently reported by {company}, {body}"
        return body[0].upper() + body[1:]

    phrase = CONCEPT_PHRASES[concept]
    tail = f"{phrase}{_segment_phrase(record)} for {period}?"
    if restated:
        # Spec 6.1: "As most recently reported" is what makes answering the
        # original figure a miss rather than a defensible reading.
        return f"As most recently reported by {company}, what was {tail}"
    return f"What was {company}'s {tail}"


def build_messages(
    record: dict[str, Any], ticker: str | None = None
) -> list[dict[str, str]]:
    """The two-message payload sent to every model for one question.

    Prefer a frozen `question` field when present so a later wording change
    cannot silently rewrite what was asked.
    """
    text = record.get("question") or question_text(record, ticker)
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"{text}\n\n{_INSTRUCTIONS}"},
    ]
