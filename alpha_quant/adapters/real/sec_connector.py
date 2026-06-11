import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from alpha_quant.adapters.real.base_connector import BaseConnector
from alpha_quant.domain.models import TickerRecord

logger = structlog.get_logger()

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
CACHE_KEY = "company_tickers"
CACHE_TTL = timedelta(days=7)


class SECConnector(BaseConnector):
    def __init__(
        self,
        *,
        user_agent: str,
        cache_path: str | Path = "sec_cache.sqlite",
        vault_base: Path | None = None,
    ) -> None:
        self._cache_path = Path(cache_path)
        self._cache_conn = sqlite3.connect(str(self._cache_path))
        self._cache_conn.execute(
            "CREATE TABLE IF NOT EXISTS sec_cache ("
            "  cache_key TEXT PRIMARY KEY,"
            "  data_json TEXT NOT NULL,"
            "  fetched_at TEXT NOT NULL"
            ")"
        )
        self._cache_conn.commit()

        super().__init__(
            source_name="sec",
            tokens_per_second=1.0,
            max_burst=1.0,
            user_agent=user_agent,
            vault_base=vault_base,
        )

    def parse(self, data: bytes, **kwargs: Any) -> Any:
        return json.loads(data)

    def _cache_fresh(self) -> bool:
        row = self._cache_conn.execute(
            "SELECT fetched_at FROM sec_cache WHERE cache_key = ?",
            (CACHE_KEY,),
        ).fetchone()
        if row is None:
            return False
        fetched = datetime.fromisoformat(row[0])
        return (datetime.now(UTC) - fetched) < CACHE_TTL

    def _read_cache(self) -> dict[str, TickerRecord] | None:
        row = self._cache_conn.execute(
            "SELECT data_json FROM sec_cache WHERE cache_key = ?",
            (CACHE_KEY,),
        ).fetchone()
        if row is None:
            return None
        return _parse_tickers(json.loads(row[0]))

    def _write_cache(self, raw: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat()
        self._cache_conn.execute(
            "INSERT OR REPLACE INTO sec_cache (cache_key, data_json, fetched_at) VALUES (?, ?, ?)",
            (CACHE_KEY, json.dumps(raw), now),
        )
        self._cache_conn.commit()

    def ticker_map(self) -> dict[str, TickerRecord]:
        if self._cache_fresh():
            cached = self._read_cache()
            if cached is not None:
                return cached

        try:
            url = SEC_TICKERS_URL
            response = self.fetch(url)
            raw: dict[str, Any] = response.json()
            self._write_cache(raw)
            result = _parse_tickers(raw)
            if result is None:
                raise RuntimeError("Failed to parse ticker data")
            return result
        except Exception as exc:
            logger.warning("sec_fetch_failed", error=str(exc))
            cached = self._read_cache()
            if cached is not None:
                logger.info("sec_fallback_to_cache")
                return cached
            raise

    def close(self) -> None:
        self._cache_conn.close()
        super().close()


def _parse_tickers(raw: dict[str, Any]) -> dict[str, TickerRecord] | None:
    if not isinstance(raw, dict):
        return None
    result: dict[str, TickerRecord] = {}
    for entry in raw.values():
        if not isinstance(entry, dict):
            continue
        ticker = (entry.get("ticker") or "").strip().upper()
        cik_raw = entry.get("cik_str")
        title = (entry.get("title") or "").strip()
        if not ticker or not cik_raw or not title:
            continue
        cik = str(int(cik_raw)).zfill(10)
        result[ticker] = TickerRecord(
            ticker=ticker,
            cik=cik,
            name=title,
        )
    return result if result else None
