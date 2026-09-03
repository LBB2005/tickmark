"""EDGAR endpoints and CIK resolution.

CIK is the only stable company identifier. Tickers get reassigned and entity
names change on every rebrand, so tickers are resolved to CIKs exactly once,
written to config/companies.yaml, and never resolved again at run time.
"""
from __future__ import annotations

from dataclasses import dataclass

from .http import SecClient

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FILING_INDEX = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/index.json"
FILING_PAGE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{dashed}-index.htm"


@dataclass(frozen=True)
class Company:
    cik: int
    ticker: str
    name: str


def normalise_ticker(ticker: str) -> str:
    """SEC writes class shares with a hyphen: BRK.B is BRK-B in their file."""
    return ticker.strip().upper().replace(".", "-")


def build_ticker_index(payload: dict) -> dict[str, Company]:
    index: dict[str, Company] = {}
    for row in payload.values():
        ticker = normalise_ticker(row["ticker"])
        index[ticker] = Company(int(row["cik_str"]), ticker, row["title"])
    return index


def companyfacts_url(cik: int) -> str:
    return COMPANYFACTS.format(cik=cik)


def submissions_url(cik: int) -> str:
    return SUBMISSIONS.format(cik=cik)


def filing_index_url(cik: int, accession: str) -> str:
    return FILING_INDEX.format(cik=cik, accn=accession.replace("-", ""))


def filing_page_url(cik: int, accession: str) -> str:
    """Human-readable filing page - this is what goes in gold.source_url."""
    return FILING_PAGE.format(
        cik=cik, accn=accession.replace("-", ""), dashed=accession)


def fetch_ticker_index(client: SecClient) -> dict[str, Company]:
    return build_ticker_index(client.get_json(TICKERS_URL))


def fetch_companyfacts(client: SecClient, cik: int) -> dict:
    return client.get_json(companyfacts_url(cik))


def fetch_submissions(client: SecClient, cik: int) -> dict:
    return client.get_json(submissions_url(cik))
