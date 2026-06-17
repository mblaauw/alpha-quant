"""Tiingo market data adapter — free daily EOD bars via api.tiingo.com."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, override

from adapters.real.base_connector import BaseConnector
from domain.models import Bar, Quote, TradingDay
from ports.market_data import MarketData

if TYPE_CHECKING:
    from app.vault import Vault


class TiingoConnector(BaseConnector, MarketData):
    """Free daily EOD bars via Tiingo's API.

    Endpoint: GET /tiingo/daily/{symbol}/prices
    Auth: token passed as query parameter ``?token=...``
    Free tier: ~500-1000 calls/hour, full history for US stocks,
    includes adjusted close, dividends, and split factors.
    """

    def __init__(
        self,
        *,
        api_token: str,
        base_url: str = "https://api.tiingo.com",
        tokens_per_second: float = 10.0,
        max_burst: float = 20.0,
        user_agent: str = "",
        vault: Vault | None = None,
    ) -> None:
        self._api_token = api_token
        super().__init__(
            source_name="tiingo",
            base_url=base_url,
            tokens_per_second=tokens_per_second,
            max_burst=max_burst,
            user_agent=user_agent,
            vault=vault,
        )

    def _params(self, **extra: str) -> dict[str, str]:
        return {"token": self._api_token, **extra}

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self._base_url}/{path.lstrip('/')}"
        merged = self._params(**(params or {}))
        response = self.fetch(url, merged)
        return response.json()

    def _parse_bar(self, entry: dict[str, Any], symbol: str) -> Bar | None:
        raw_date = entry.get("date")
        if not raw_date:
            return None
        try:
            bar_date = datetime.fromisoformat(raw_date).date()
        except ValueError, TypeError:
            return None

        return Bar(
            symbol=symbol,
            date=bar_date,
            open=float(entry.get("open", 0) or 0),
            high=float(entry.get("high", 0) or 0),
            low=float(entry.get("low", 0) or 0),
            close=float(entry.get("close", 0) or 0),
            volume=float(entry.get("volume", 0) or 0),
            adj_close=float(entry["adjClose"]) if entry.get("adjClose") is not None else None,
        )

    @override
    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        try:
            raw = self._get_json(
                f"tiingo/daily/{symbol}/prices",
                {
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                },
            )
        except Exception:
            return []

        if not isinstance(raw, list):
            return []

        bars: list[Bar] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            bar = self._parse_bar(entry, symbol)
            if bar is not None:
                bars.append(bar)
        return bars

    @override
    def latest_quote(self, symbol: str) -> Quote:
        try:
            raw = self._get_json(
                f"tiingo/daily/{symbol}/prices",
                {
                    "sort": "-date",
                    "limit": "1",
                },
            )
        except Exception:
            return Quote(symbol=symbol, timestamp=datetime.now(UTC), price=None)

        if not isinstance(raw, list) or not raw:
            return Quote(symbol=symbol, timestamp=datetime.now(UTC), price=None)

        entry = raw[0]
        close = float(entry.get("close", 0) or 0)
        return Quote(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            price=close,
            bid=close,
            ask=close,
        )

    @override
    def trading_calendar(self, start: date, end: date) -> list[TradingDay]:
        """Weekday-based trading calendar (no market holidays)."""
        days: list[TradingDay] = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                days.append(
                    TradingDay(
                        date=current,
                        is_open=True,
                        session="regular",
                    )
                )
            current += timedelta(days=1)
        return days
