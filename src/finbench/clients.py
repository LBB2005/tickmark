"""OpenRouter client with hard provider pinning.

Ported from the AEO Portfolio Index, whose Phase 0 probe already paid for the
per-provider quirks encoded in config/models.yaml.

Left alone, OpenRouter reroutes across upstream providers and quantisations. A
silently substituted copy from a different host is a different measurement
wearing the same label, so:

  * fallbacks off, so substitution fails loudly rather than quietly;
  * the RESOLVED provider and model are recorded on every row;
  * a resolved/requested mismatch quarantines the call instead of scoring it.

That is what makes spec section 7.3's reproducibility claim true rather than
aspirational.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

API = "https://openrouter.ai/api/v1/chat/completions"


@dataclass
class CallResult:
    ok: bool
    model_id: str
    requested_slug: str
    temperature_sent: float | None
    resolved_model: str | None
    resolved_provider: str | None
    quarantined: bool
    quarantine_reason: str | None
    text: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    reasoning_tokens: int | None
    cost_usd: float | None
    latency_ms: int
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Transient(Exception):
    pass


class OpenRouterClient:
    def __init__(self, api_key: str | None = None, timeout: float = 180.0):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        self._http = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> OpenRouterClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @retry(retry=retry_if_exception_type(Transient),
           stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=2, min=2, max=30),
           reraise=True)
    def _post(self, body: dict[str, Any]) -> httpx.Response:
        response = self._http.post(
            API,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json",
                     "X-Title": "finbench-calibration"},
            json=body,
        )
        if response.status_code in (408, 429, 500, 502, 503, 504):
            raise Transient(f"{response.status_code}: {response.text[:200]}")
        return response

    def build_body(self, model: dict[str, Any], prompt: str | None = None, *,
                   temperature: float, max_tokens: int,
                   messages: list[dict[str, str]] | None = None) -> dict[str, Any]:
        if messages is None:
            if prompt is None:
                raise ValueError("prompt or messages is required")
            messages = [{"role": "user", "content": prompt}]
        body: dict[str, Any] = {
            "model": model["slug"],
            "messages": messages,
            "max_tokens": max_tokens,
            "provider": {
                "only": model["provider_tags"],
                "allow_fallbacks": False,
                "require_parameters": True,
            },
            "usage": {"include": True},
        }
        # Only send temperature where the pinned endpoint advertises it:
        # require_parameters turns an unsupported param into zero endpoints and
        # a 404, not a silently ignored field.
        if model.get("send_temperature", True):
            body["temperature"] = temperature
        if model.get("reasoning") is not None:
            body["reasoning"] = model["reasoning"]
        return body

    def _fail(self, model: dict, reason: str, error: str, latency: int) -> CallResult:
        return CallResult(
            ok=False, model_id=model["id"], requested_slug=model["slug"],
            temperature_sent=None, resolved_model=None, resolved_provider=None,
            quarantined=True, quarantine_reason=reason, text=None,
            prompt_tokens=None, completion_tokens=None, reasoning_tokens=None,
            cost_usd=None, latency_ms=latency, error=error[:500])

    def call(self, *, model: dict[str, Any], prompt: str | None = None,
             messages: list[dict[str, str]] | None = None,
             temperature: float = 0.0, max_tokens: int = 700) -> CallResult:
        body = self.build_body(model, prompt, temperature=temperature,
                               max_tokens=max_tokens, messages=messages)
        start = time.perf_counter()
        try:
            response = self._post(body)
        except Exception as exc:  # noqa: BLE001
            return self._fail(model, "request_failed", str(exc),
                              int((time.perf_counter() - start) * 1000))
        latency = int((time.perf_counter() - start) * 1000)

        if response.status_code != 200:
            return self._fail(model, "http_error",
                              f"{response.status_code}: {response.text[:400]}", latency)

        payload = response.json()
        if "error" in payload and not payload.get("choices"):
            return self._fail(model, "api_error",
                              json.dumps(payload["error"]), latency)

        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = payload.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        resolved_model = payload.get("model")
        resolved_provider = payload.get("provider")

        quarantined, reason = False, None
        if resolved_model and resolved_model != model["slug"]:
            quarantined, reason = True, f"model_substituted:{resolved_model}"
        elif resolved_provider and model.get("provider_names") and \
                resolved_provider.lower() not in [p.lower() for p in model["provider_names"]]:
            quarantined, reason = True, f"provider_substituted:{resolved_provider}"

        return CallResult(
            ok=True, model_id=model["id"], requested_slug=model["slug"],
            temperature_sent=body.get("temperature"),
            resolved_model=resolved_model, resolved_provider=resolved_provider,
            quarantined=quarantined, quarantine_reason=reason,
            text=message.get("content"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            reasoning_tokens=details.get("reasoning_tokens"),
            cost_usd=usage.get("cost"), latency_ms=latency, error=None,
        )
