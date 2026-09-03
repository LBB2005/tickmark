import time

import pytest

from finbench.http import SecClient, user_agent


def test_user_agent_requires_contact_email(monkeypatch):
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="SEC_CONTACT_EMAIL"):
        user_agent()


def test_user_agent_includes_email(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "a@b.com")
    assert "a@b.com" in user_agent()


def test_throttle_enforces_minimum_interval(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "a@b.com")
    client = SecClient(min_interval=0.05, cache_dir=None)
    start = time.monotonic()
    client._throttle("data.sec.gov")
    client._throttle("data.sec.gov")
    assert time.monotonic() - start >= 0.05
    client.close()


def test_cache_key_is_stable_and_path_safe(monkeypatch, tmp_path):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "a@b.com")
    client = SecClient(cache_dir=tmp_path)
    url = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
    first = client._cache_path(url)
    assert first == client._cache_path(url)
    assert "/" not in first.name
    client.close()


def test_get_json_reads_from_cache_without_network(monkeypatch, tmp_path):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "a@b.com")
    client = SecClient(cache_dir=tmp_path)
    url = "https://data.sec.gov/x.json"
    client._cache_path(url).write_text('{"cached": true}')

    def explode(*_args, **_kwargs):
        raise AssertionError("network must not be touched on a cache hit")

    monkeypatch.setattr(client._client, "get", explode)
    assert client.get_json(url) == {"cached": True}
    client.close()


def test_download_to_streams_to_disk(monkeypatch, tmp_path):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "a@b.com")
    client = SecClient(cache_dir=None)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_bytes(self, chunk_size=None):
            yield b"abc"
            yield b"def"

    class FakeStream:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(client._client, "stream", lambda *a, **k: FakeStream())
    out = client.download_to("https://x/y.zip", tmp_path / "sub" / "y.zip")
    assert out.read_bytes() == b"abcdef"
    client.close()
