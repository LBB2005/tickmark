"""The single outbound HTTP path for SEC data.

Politeness is enforced here so no caller can skip it: an identifying
User-Agent (SEC requires one and blocks anonymous traffic), a per-domain
throttle, and retries on transport errors, 429 and 5xx only.

Every response is also cached to disk. The screen and the gold assembly each
read the same ~1MB companyfacts document for 58 companies; without a cache
that is hundreds of needless requests and a pipeline you cannot debug offline.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

PROJECT_NAME = "FinBench Calibration (research benchmark)"
MIN_INTERVAL_SECONDS = 0.15  # SEC permits ~10 req/s; this is ~6.7 req/s
TIMEOUT_SECONDS = 60.0
DEFAULT_CACHE = pathlib.Path(__file__).resolve().parents[2] / "data" / "cache" / "edgar"


def user_agent() -> str:
    """Build the User-Agent. Raises if no contact email is configured.

    Fails loudly on purpose: a silent anonymous fallback would make every
    request impolite without anyone noticing, and SEC blocks on it.
    """
    email = os.environ.get("SEC_CONTACT_EMAIL", "").strip()
    if not email:
        raise RuntimeError(
            "SEC_CONTACT_EMAIL is not set. Every SEC request must identify the "
            "project with a real email address. See .env.example."
        )
    return f"{PROJECT_NAME} {email}"


def _is_retryable(exc: BaseException) -> bool:
    """Transport errors, 429 and 5xx only. A 404 is a definitive answer."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status >= 500 or status == 429
    return False


class SecClient:
    def __init__(
        self,
        min_interval: float = MIN_INTERVAL_SECONDS,
        cache_dir: pathlib.Path | None = DEFAULT_CACHE,
    ) -> None:
        self._min_interval = min_interval
        self._cache_dir = pathlib.Path(cache_dir) if cache_dir else None
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_at: dict[str, float] = {}
        self._client = httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True)

    def _throttle(self, domain: str) -> None:
        last = self._last_request_at.get(domain)
        if last is not None:
            elapsed = time.monotonic() - last
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
        self._last_request_at[domain] = time.monotonic()

    def _cache_path(self, url: str) -> pathlib.Path:
        assert self._cache_dir is not None
        stem = hashlib.sha256(url.encode()).hexdigest()[:24]
        tail = urlparse(url).path.rsplit("/", 1)[-1][:40].replace("/", "_")
        return self._cache_dir / f"{stem}-{tail or 'index'}"

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        self._throttle(urlparse(url).netloc)
        headers = {"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"}
        headers.update(kwargs.pop("headers", None) or {})
        response = self._client.get(url, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def get_text(self, url: str, *, use_cache: bool = True) -> str:
        if self._cache_dir and use_cache:
            path = self._cache_path(url)
            if path.exists():
                return path.read_text(encoding="utf-8")
            text = self._get(url).text
            path.write_text(text, encoding="utf-8")
            return text
        return self._get(url).text

    def get_json(self, url: str, *, use_cache: bool = True) -> Any:
        return json.loads(self.get_text(url, use_cache=use_cache))

    def get_bytes(self, url: str) -> bytes:
        """Uncached - for large zip archives the caller stores itself."""
        return self._get(url).content

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SecClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
