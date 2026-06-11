from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
)

from alpha_quant.adapters.real.token_bucket import TokenBucket

if TYPE_CHECKING:
    from alpha_quant.app.vault import Vault

logger = structlog.get_logger()


def _is_retryable(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in {429, 500, 502, 503, 504}
    return isinstance(exception, httpx.RequestError)


def _wait(retry_state: Any) -> float:
    outcome = retry_state.outcome
    if outcome is not None:
        exc = outcome.exception()
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
            retry_after = exc.response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return float(retry_after)
                except ValueError, TypeError:
                    pass
    return min(2 * (2**retry_state.attempt_number), 30)


def _parse_date(value: str | None, *fmts: str) -> date | None:
    if not value:
        return None
    formats = fmts or ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y")
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError, TypeError:
            continue
    return None


class BaseConnector:
    def __init__(
        self,
        source_name: str,
        *,
        base_url: str = "",
        tokens_per_second: float = 10.0,
        max_burst: float = 20.0,
        timeout_s: float = 30.0,
        user_agent: str = "",
        vault: Vault | None = None,
    ):
        self._source_name = source_name
        self._base_url = base_url.rstrip("/")
        self._bucket = TokenBucket(tokens_per_second, max_burst)
        self._vault = vault

        headers = {}
        if user_agent:
            headers["User-Agent"] = user_agent
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_s),
            headers=headers,
            follow_redirects=True,
        )

    def parse(self, data: bytes, **kwargs: Any) -> Any:
        return data

    def _do_request(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        for attempt in Retrying(
            stop=stop_after_attempt(5),
            wait=_wait,
            retry=retry_if_exception(_is_retryable),
            before_sleep=before_sleep_log(logger, logging.WARN),
            reraise=True,
        ):
            with attempt:
                response = self._client.get(url, params=params)
                response.raise_for_status()
                return response
        raise RuntimeError("Unreachable")

    def fetch(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        while not self._bucket.consume():
            time.sleep(self._bucket.wait_time())

        start = time.monotonic()
        response = self._do_request(url, params)
        latency = time.monotonic() - start

        logger.debug(
            "http_fetch",
            source=self._source_name,
            url=url,
            status=response.status_code,
            latency_ms=round(latency * 1000),
            byte_size=len(response.content),
        )

        if self._vault is not None:
            query_params = {}
            if params:
                query_params = dict(sorted(params.items()))
            self._vault.store(
                source=self._source_name,
                endpoint=url,
                params=query_params,
                data=response.content,
            )

        return response

    def close(self) -> None:
        self._client.close()
