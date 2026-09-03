import pytest

from finbench import gold


def _record(**overrides):
    base = dict(
        question_id="rst-0001", company="Testco", cik=1,
        fiscal_period="fiscal 2023 (year ended December 31, 2023)",
        fiscal_period_end="2023-12-31", concept="Revenues",
        answer_type="numeric", gold_value=900.0, gold_unit="USD",
        superseded_value=1000.0, source_accession="0001-24-000001",
        source_form="10-K", source_filed_date="2025-02-01",
        source_url="https://sec.gov/x", category="restatement",
        difficulty="mid", verification="auto", verified_by=None,
        verified_date=None,
    )
    base.update(overrides)
    return base


def test_valid_record_round_trips():
    assert gold.validate(_record())["gold_value"] == 900.0


def test_none_exists_must_not_carry_a_value():
    with pytest.raises(ValueError, match="gold_value"):
        gold.validate(_record(answer_type="none_exists", gold_value=5.0))


def test_none_exists_with_null_value_is_valid():
    assert gold.validate(_record(answer_type="none_exists", gold_value=None))


def test_post_cutoff_must_not_carry_a_value():
    with pytest.raises(ValueError, match="gold_value"):
        gold.validate(_record(answer_type="post_cutoff", gold_value=1.0))


def test_numeric_requires_a_value():
    with pytest.raises(ValueError, match="gold_value"):
        gold.validate(_record(answer_type="numeric", gold_value=None))


def test_unknown_answer_type_rejected():
    with pytest.raises(ValueError, match="answer_type"):
        gold.validate(_record(answer_type="probably"))


def test_unknown_category_rejected():
    with pytest.raises(ValueError, match="category"):
        gold.validate(_record(category="vibes"))


def test_missing_field_is_named():
    record = _record()
    del record["source_url"]
    with pytest.raises(ValueError, match="source_url"):
        gold.validate(record)


def test_writer_round_trips_through_jsonl(tmp_path):
    path = tmp_path / "gold.jsonl"
    gold.write([_record(), _record(question_id="rst-0002")], path)
    assert len(gold.read(path)) == 2


def test_duplicate_question_ids_rejected(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        gold.write([_record(), _record()], tmp_path / "g.jsonl")


def test_post_cutoff_actual_is_allowed_and_preserved(tmp_path):
    # The true value is kept out of gold_value so the record cannot be scored
    # as answerable, but is retained so per-model cutoff boundaries can score
    # it either way later (spec 7.4).
    record = _record(answer_type="post_cutoff", gold_value=None,
                     category="post_cutoff", post_cutoff_actual=1234.0)
    path = tmp_path / "g.jsonl"
    gold.write([record], path)
    assert gold.read(path)[0]["post_cutoff_actual"] == 1234.0
