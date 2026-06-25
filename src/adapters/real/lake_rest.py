from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, override

import httpx

from domain.calendar import is_market_day
from domain.models import (
    Bar,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
    TradingDay,
)
from ports.lake import LakeGateway


class RestLakeGateway(LakeGateway):
    """HTTP client adapter for the Alpha-Lake REST API.

    Connects to a running alpha-lake Docker container via its REST interface.
    All reads are bounded by ``as_of`` for point-in-time determinism.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
        price_mode: str = "split_adjusted",
        timeout_s: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-API-Key": api_key} if api_key else {}
        self._price_mode = price_mode
        self._timeout_s = timeout_s
        self._snapshot_id: str | None = None
        self._client = httpx.Client(timeout=httpx.Timeout(timeout_s))

    @override
    def pin_snapshot(self, snapshot_id: str | None) -> None:
        self._snapshot_id = snapshot_id or None

    @override
    def dataset_health(self) -> dict[str, object]:
        params: dict[str, str] = {}
        if self._snapshot_id:
            params["snapshot_id"] = self._snapshot_id
        resp = self._client.get(
            f"{self._base_url}/v1/dataset-health", headers=self._headers, params=params
        )
        resp.raise_for_status()
        return resp.json()

    @override
    def bars(
        self,
        symbol: str,
        start: date,
        end: date,
        as_of: datetime,
        price_mode: str = "split_adjusted",
    ) -> list[Bar]:
        params: dict[str, str] = {
            "symbol": symbol,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "as_of": as_of.isoformat(),
            "price_mode": price_mode or self._price_mode,
        }
        if self._snapshot_id:
            params["snapshot_id"] = self._snapshot_id
        resp = self._client.get(f"{self._base_url}/v1/bars", headers=self._headers, params=params)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return [self._parse_bar(row, symbol) for row in resp.json()]

    @override
    def latest_bar(self, symbol: str, as_of: datetime) -> Bar | None:
        start = as_of.date() - timedelta(days=10)
        bars = self.bars(symbol, start, as_of.date(), as_of)
        return bars[-1] if bars else None

    @override
    def trading_calendar(self, start: date, end: date) -> list[TradingDay]:
        params: dict[str, str] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        if self._snapshot_id:
            params["snapshot_id"] = self._snapshot_id
        resp = self._client.get(
            f"{self._base_url}/v1/trading-calendar", headers=self._headers, params=params
        )
        if resp.status_code == 200:
            data = resp.json()
            return [
                TradingDay(
                    date=datetime.fromisoformat(d["date"]).date(),
                    is_open=d["is_open"],
                    session=d.get("session"),
                )
                for d in data.get("days", [])
            ]
        days: list[TradingDay] = []
        current = start
        while current <= end:
            open_day = is_market_day(current)
            days.append(
                TradingDay(
                    date=current,
                    is_open=open_day,
                    session="regular" if open_day else None,
                )
            )
            current += timedelta(days=1)
        return days

    @override
    def fundamentals(self, symbol: str, as_of: datetime) -> FundamentalsSnapshot | None:
        try:
            resp = self._client.get(
                f"{self._base_url}/v1/fundamentals/metrics",
                headers=self._headers,
                params={
                    "symbol": symbol,
                    "as_of": as_of.isoformat(),
                    "categories": "valuation,profitability,growth,financial_health",
                    "include": "provenance",
                },
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            metrics = data.get("metrics", [])
            if not metrics:
                return None
            by_id: dict[str, float | None] = {}
            for m in metrics:
                mid = m.get("metric_id")
                val = m.get("value")
                if mid is not None:
                    by_id[mid] = float(val) if val is not None else None
            return FundamentalsSnapshot(
                symbol=symbol,
                as_of_date=as_of.date(),
                market_cap=by_id.get("market_cap"),
                pe_ratio=by_id.get("pe_ratio"),
                eps_ttm=by_id.get("eps_ttm"),
                dividend_yield=by_id.get("dividend_yield"),
                operating_cash_flow=by_id.get("operating_cash_flow"),
                total_liabilities=by_id.get("total_liabilities"),
                total_debt=by_id.get("total_debt"),
                total_equity=by_id.get("total_equity"),
                revenue=by_id.get("revenue"),
                net_income=by_id.get("net_income"),
                accruals=by_id.get("accruals"),
                adapter="alpha_lake_rest",
            )
        except httpx.HTTPError:
            return None

    @override
    def earnings_calendar(self, start: date, end: date, as_of: datetime) -> list[EarningsEntry]:
        params: dict[str, str] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "as_of": as_of.isoformat(),
        }
        if self._snapshot_id:
            params["snapshot_id"] = self._snapshot_id
        try:
            resp = self._client.get(
                f"{self._base_url}/v1/earnings-calendar", headers=self._headers, params=params
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            return [
                EarningsEntry(
                    symbol=str(e.get("symbol", e.get("security_id", ""))),
                    date=self._parse_date(e.get("effective_date") or e.get("date")),
                    adapter="alpha_lake_rest",
                )
                for e in data.get("earnings", [])
            ]
        except httpx.HTTPError:
            return []

    @override
    def insider_transactions(self, symbol: str, as_of: datetime) -> list[InsiderTransaction]:
        params: dict[str, str] = {"as_of": as_of.isoformat()}
        if self._snapshot_id:
            params["snapshot_id"] = self._snapshot_id
        try:
            resp = self._client.get(
                f"{self._base_url}/v1/insider-transactions/{symbol}",
                headers=self._headers,
                params=params,
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            return [
                InsiderTransaction(
                    symbol=symbol,
                    filing_date=self._parse_date(t.get("effective_date") or t.get("filing_date")),
                    transaction_date=self._parse_date(
                        t.get("transaction_date") or t.get("effective_date")
                    ),
                    owner=str(t.get("filer_cik") or t.get("owner") or "unknown"),
                    transaction_type=str(
                        t.get("transaction_code") or t.get("transaction_type") or ""
                    ),
                    shares_traded=float(t.get("shares") or t.get("shares_traded") or 0.0),
                    price=self._opt_float(t.get("price")),
                    shares_held=self._opt_float(t.get("shares_held")),
                    adapter="alpha_lake_rest",
                )
                for t in data.get("transactions", [])
            ]
        except httpx.HTTPError:
            return []

    @override
    def mention_counts(self, symbol: str, days: int, as_of: datetime) -> list[MentionCount]:
        params: dict[str, str] = {"days": str(days), "as_of": as_of.isoformat()}
        if self._snapshot_id:
            params["snapshot_id"] = self._snapshot_id
        try:
            resp = self._client.get(
                f"{self._base_url}/v1/attention-metrics/{symbol}",
                headers=self._headers,
                params=params,
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            return [
                MentionCount(
                    symbol=symbol,
                    mention_date=self._parse_date(m.get("effective_date") or m.get("date")),
                    source=str(m.get("source_id") or "alpha_lake_attention"),
                    count=int(m.get("mention_count") or m.get("count") or 0),
                    adapter="alpha_lake_rest",
                )
                for m in data.get("mentions", [])
            ]
        except httpx.HTTPError:
            return []

    def _parse_bar(self, row: dict[str, Any], symbol: str) -> Bar:
        return Bar(
            symbol=symbol,
            date=self._parse_date(row.get("effective_date") or row.get("date")),
            open=float(row.get("open", 0.0)),
            high=float(row.get("high", 0.0)),
            low=float(row.get("low", 0.0)),
            close=float(row.get("close", 0.0)),
            volume=float(row.get("volume", 0.0)),
            adj_close=self._opt_float(row.get("adj_close") or row.get("adjusted_close")),
            adapter="alpha_lake_rest",
        )

    def _parse_date(self, raw: Any) -> date:
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        if isinstance(raw, str):
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        return date.today()

    def _opt_float(self, raw: Any) -> float | None:
        if raw is None:
            return None
        return float(raw)

    def close(self) -> None:
        self._client.close()
