import json
import pathlib

from finbench import observations

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "facts_mini.json"


def load():
    return json.loads(FIXTURE.read_text())


def test_flattens_every_observation():
    obs = list(observations.iter_observations(load()))
    assert len(obs) == 3
    assert {o.concept for o in obs} == {"Revenues"}


def test_carries_provenance_fields():
    first = next(iter(observations.iter_observations(load())))
    assert first.accn == "0001-23-000001"
    assert first.form == "10-K"
    assert first.filed == "2024-02-01"
    assert first.unit == "USD"


def test_period_key_uses_start_and_end_not_fy():
    obs = list(observations.iter_observations(load()))
    original, restated = obs[0], obs[1]
    assert original.fy != restated.fy
    assert original.period_key == restated.period_key


def test_dei_taxonomy_is_reachable():
    obs = list(observations.iter_observations(load(), taxonomy="dei"))
    assert len(obs) == 1
    assert obs[0].concept == "EntityPublicFloat"


def test_instant_facts_have_no_start():
    obs = list(observations.iter_observations(load(), taxonomy="dei"))
    assert obs[0].is_instant


def test_public_float_extracts_latest_value():
    assert observations.public_float(load()) == 5000000000


def test_public_float_is_none_when_absent():
    assert observations.public_float({"facts": {}}) is None
