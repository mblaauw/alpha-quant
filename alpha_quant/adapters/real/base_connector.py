import logging
import time
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import structlog
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
)

from alpha_quant.adapters.real.token_bucket import TokenBucket

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


class BaseConnector(ABC):
    def __init__(
        self,
        source_name: str,
        *,
        base_url: str = "",
        tokens_per_second: float = 10.0,
        max_burst: float = 20.0,
        timeout_s: float = 30.0,
        user_agent: str = "",
        vault_base: Path | None = None,
    ):
        self._source_name = source_name
        self._base_url = base_url.rstrip("/")
        self._bucket = TokenBucket(tokens_per_second, max_burst)
        self._vault_base = vault_base

        headers = {}
        if user_agent:
            headers["User-Agent"] = user_agent
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_s),
            headers=headers,
            follow_redirects=True,
        )

    @abstractmethod
    def parse(self, data: bytes, **kwargs: Any) -> Any: ...

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

        if self._vault_base is not None:
            from alpha_quant.app.vault import write_blob

            query_str = ""
            if params:
                query_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            write_blob(
                base=self._vault_base,
                source=self._source_name,
                dt=date.today(),
                endpoint=url,
                params=query_str,
                data=response.content,
            )

        return response

    def close(self) -> None:
        self._client.close()
