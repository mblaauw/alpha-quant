from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
)

from adapters.real.token_bucket import TokenBucket

if TYPE_CHECKING:
    from app.vault import Vault


@dataclass
class FetchResult:
    response: httpx.Response
    fetch_id: str | None = None


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
                except (ValueError, TypeError):  # fmt: skip
                    pass
    return min(2 * (2**retry_state.attempt_number), 30)


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
        auth: tuple[str, str] | None = None,
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
            auth=auth,
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

    def fetch_with_lineage(self, url: str, params: dict[str, str] | None = None) -> FetchResult:
        while not self._bucket.consume():
            time.sleep(self._bucket.wait_time())

        start = time.monotonic()
        response = self._do_request(url, params)
        latency = time.monotonic() - start

        # Strip sensitive query params before logging
        safe_url = url.split("?")[0] if "?" in url else url
        safe_params = None
        if params:
            sensitive_keys = {"api_token", "apikey", "api_key", "secret", "token", "key"}
            safe_params = {
                k: ("***" if k.lower() in sensitive_keys else v) for k, v in params.items()
            }

        logger.debug(
            "http_fetch",
            source=self._source_name,
            url=safe_url,
            params=safe_params,
            status=response.status_code,
            latency_ms=round(latency * 1000),
            byte_size=len(response.content),
        )

        fetch_id: str | None = None
        if self._vault is not None:
            query_params = {}
            if params:
                query_params = dict(sorted(params.items()))
            fetch_id = self._vault.store(
                source=self._source_name,
                endpoint=url,
                params=query_params,
                data=response.content,
            )

        return FetchResult(response=response, fetch_id=fetch_id)

    def fetch(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        fr = self.fetch_with_lineage(url, params)
        return fr.response

    def close(self) -> None:
        self._client.close()

    def check_connection(self) -> bool:
        try:
            resp = self._client.get(self._base_url, timeout=5.0)
            return resp.status_code < 500
        except Exception:
            return False
