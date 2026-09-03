import os

from finbench import config


def test_real_env_beats_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('FINBENCH_T1="from-file"\n')
    monkeypatch.setenv("FINBENCH_T1", "from-env")
    config.load_dotenv(env)
    assert os.environ["FINBENCH_T1"] == "from-env"


def test_dotenv_fills_when_unset(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FINBENCH_T2=xyz\n# a comment\n\n")
    monkeypatch.delenv("FINBENCH_T2", raising=False)
    config.load_dotenv(env)
    assert os.environ["FINBENCH_T2"] == "xyz"


def test_missing_dotenv_is_not_an_error(tmp_path):
    config.load_dotenv(tmp_path / "nope.env")


def test_config_hash_changes_with_content(tmp_path):
    (tmp_path / "a.yaml").write_text("x: 1\n")
    first = config.config_hash(tmp_path)
    (tmp_path / "a.yaml").write_text("x: 2\n")
    assert config.config_hash(tmp_path) != first
