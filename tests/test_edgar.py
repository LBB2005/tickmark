from finbench import edgar


def test_normalises_dotted_and_dashed_tickers():
    assert edgar.normalise_ticker("BRK.B") == "BRK-B"
    assert edgar.normalise_ticker("brk-b") == "BRK-B"
    assert edgar.normalise_ticker(" GE ") == "GE"


def test_builds_ticker_index_from_sec_payload():
    payload = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
    }
    index = edgar.build_ticker_index(payload)
    assert index["AAPL"].cik == 320193
    assert index["BRK-B"].name == "BERKSHIRE HATHAWAY INC"


def test_companyfacts_url_zero_pads_to_ten_digits():
    assert edgar.companyfacts_url(320193).endswith("CIK0000320193.json")


def test_filing_index_url_strips_accession_dashes():
    url = edgar.filing_index_url(320193, "0000320193-24-000123")
    assert "000032019324000123" in url
