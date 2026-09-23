import pytest

from finbench.clients import OpenRouterClient

MODEL = {"id": "m", "slug": "lab/model", "provider_tags": ["lab"],
         "provider_names": ["Lab"], "send_temperature": True,
         "reasoning": {"enabled": False}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    c = OpenRouterClient()
    yield c
    c.close()


def test_missing_key_fails_loudly(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterClient()


def test_body_pins_provider_and_disables_fallbacks(client):
    body = client.build_body(MODEL, "hi", temperature=0.0, max_tokens=10)
    assert body["provider"] == {"only": ["lab"], "allow_fallbacks": False,
                                "require_parameters": True}
    assert body["usage"] == {"include": True}


def test_temperature_omitted_where_endpoint_rejects_it(client):
    model = {**MODEL, "send_temperature": False}
    assert "temperature" not in client.build_body(model, "hi", temperature=0.0, max_tokens=10)
    assert client.build_body(MODEL, "hi", temperature=0.0, max_tokens=10)["temperature"] == 0.0


def test_reasoning_omitted_when_null(client):
    model = {**MODEL, "reasoning": None}
    assert "reasoning" not in client.build_body(model, "hi", temperature=0.0, max_tokens=10)


def test_model_substitution_is_quarantined(client, monkeypatch):
    class R:
        status_code = 200
        def json(self):
            return {"model": "lab/other-model", "provider": "Lab",
                    "choices": [{"message": {"content": "x"}}], "usage": {}}
    monkeypatch.setattr(client, "_post", lambda body: R())
    result = client.call(model=MODEL, prompt="hi")
    assert result.quarantined
    assert result.quarantine_reason == "model_substituted:lab/other-model"


def test_provider_substitution_is_quarantined(client, monkeypatch):
    class R:
        status_code = 200
        def json(self):
            return {"model": "lab/model", "provider": "SomeoneElse",
                    "choices": [{"message": {"content": "x"}}], "usage": {}}
    monkeypatch.setattr(client, "_post", lambda body: R())
    result = client.call(model=MODEL, prompt="hi")
    assert result.quarantined
    assert result.quarantine_reason == "provider_substituted:SomeoneElse"


def test_clean_call_is_not_quarantined(client, monkeypatch):
    class R:
        status_code = 200
        def json(self):
            return {"model": "lab/model", "provider": "Lab",
                    "choices": [{"message": {"content": "answer"}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 4, "cost": 0.01}}
    monkeypatch.setattr(client, "_post", lambda body: R())
    result = client.call(model=MODEL, prompt="hi")
    assert result.ok and not result.quarantined
    assert result.text == "answer" and result.cost_usd == 0.01


def test_messages_are_sent_when_provided(client):
    messages = [{"role": "system", "content": "sys"},
                {"role": "user", "content": "hi"}]
    body = client.build_body(MODEL, temperature=0.0, max_tokens=10,
                             messages=messages)
    assert body["messages"] == messages


def test_http_error_becomes_a_failed_result_not_an_exception(client, monkeypatch):
    class R:
        status_code = 404
        text = "no endpoints"
    monkeypatch.setattr(client, "_post", lambda body: R())
    result = client.call(model=MODEL, prompt="hi")
    assert not result.ok and result.quarantine_reason == "http_error"
