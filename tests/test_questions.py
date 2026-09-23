"""Frozen questions are rendered gold records, never freehand prose."""
from __future__ import annotations

import hashlib
import json

from finbench import gold, questions
from finbench.config import DATA_DIR


def _record(**overrides):
    base = dict(
        question_id="rst-0001", company="GENERAL ELECTRIC CO", cik=40545,
        fiscal_period="the fiscal year ended December 31, 2019",
        fiscal_period_end="2019-12-31", concept="Revenues",
        answer_type="numeric", gold_value=900.0, gold_unit="USD",
        superseded_value=1000.0, source_accession="0001-24-000001",
        source_form="10-K", source_filed_date="2025-02-01",
        source_url="https://sec.gov/x", category="restatement",
        difficulty="mid", verification="auto", verified_by=None,
        verified_date=None,
    )
    base.update(overrides)
    return base


def test_a_frozen_question_carries_the_rendered_text_and_the_gold_fields():
    frozen = questions.render(_record())
    assert frozen["question"].startswith("As most recently reported by")
    assert frozen["question_id"] == "rst-0001"
    assert frozen["gold_value"] == 900.0
    assert "GENERAL ELECTRIC CO (GE)" in frozen["question"]


def test_freeze_writes_jsonl_and_a_matching_sha256(tmp_path):
    path = tmp_path / "questions.jsonl"
    digest_path = tmp_path / "QUESTIONS.sha256"
    n, digest = questions.freeze([_record(), _record(question_id="rst-0002")],
                                 path, digest_path)
    assert n == 2
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest_path.read_text().split()[0] == digest
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert all("question" in row for row in rows)


def test_every_live_gold_record_can_be_rendered():
    # The freeze is only as good as the concept map. An unmapped XBRL tag
    # must raise here, not leak into a question a model would never see.
    records = gold.read(DATA_DIR / "gold.jsonl")
    rendered = [questions.render(record) for record in records]
    assert len(rendered) == len(records)
    assert all(row["question"].endswith("?") for row in rendered)


def test_committed_question_hash_matches_the_file():
    digest = questions.sha256_file(DATA_DIR / "questions.jsonl")
    recorded = (DATA_DIR / "QUESTIONS.sha256").read_text().split()[0]
    assert digest == recorded


def test_committed_gold_hash_matches_the_file():
    digest = questions.sha256_file(DATA_DIR / "gold.jsonl")
    recorded = (DATA_DIR / "GOLD.sha256").read_text().split()[0]
    assert digest == recorded
