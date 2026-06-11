from __future__ import annotations

from datetime import UTC, date
from typing import Any, override

import structlog

from alpha_quant.adapters.real.base_connector import BaseConnector
from alpha_quant.domain.models import Bar, Quote, TradingDay
from alpha_quant.ports.market_data import MarketData

logger = structlog.get_logger()


class AlpacaConnector(BaseConnector, MarketData):
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        *,
        base_url: str = "https://data.alpaca.markets",
        tokens_per_second: float = 10.0,
        max_burst: float = 20.0,
        user_agent: str = "",
        vault: Any = None,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        super().__init__(
            source_name="alpaca",
            base_url=base_url,
            tokens_per_second=tokens_per_second,
            max_burst=max_burst,
            user_agent=user_agent,
            vault=vault,
            auth=(api_key, secret_key),
        )

    def _get_stock_client(self):
        from alpaca.data.historical import StockHistoricalDataClient

        return StockHistoricalDataClient(self._api_key, self._secret_key)

    @override
    def latest_quote(self, symbol: str) -> Quote:
        from alpaca.data.models import Quote as AlpacaQuote
        from alpaca.data.requests import StockLatestQuoteRequest

        client = self._get_stock_client()
        request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
        result = client.get_stock_latest_quote(request)
        raw: AlpacaQuote = result[symbol]

        bid = float(raw.bid_price) if raw.bid_price is not None else None
        ask = float(raw.ask_price) if raw.ask_price is not None else None
        mid = ((bid + ask) / 2) if (bid is not None and ask is not None) else None

        return Quote(
            symbol=symbol,
            timestamp=raw.timestamp.astimezone(UTC),
            price=mid,
            bid=bid,
            ask=ask,
            bid_size=float(raw.bid_size) if raw.bid_size is not None else None,
            ask_size=float(raw.ask_size) if raw.ask_size is not None else None,
        )

    @override
    def trading_calendar(self, start: date, end: date) -> list[TradingDay]:
        params: dict[str, str] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        response = self.fetch(f"{self._base_url}/v2/calendar", params)
        entries = response.json()

        return [
            TradingDay(
                date=date.fromisoformat(e["date"]),
                is_open=True,
                session="regular",
            )
            for e in entries
            if e.get("date")
        ]

    def latest_bar(self, symbol: str) -> Bar | None:
        from alpaca.data.models import Bar as AlpacaBar
        from alpaca.data.requests import StockLatestBarRequest

        client = self._get_stock_client()
        request = StockLatestBarRequest(symbol_or_symbols=[symbol])
        result = client.get_stock_latest_bar(request)
        if symbol not in result:
            return None

        raw: AlpacaBar = result[symbol]
        return Bar(
            symbol=symbol,
            date=raw.timestamp.date(),
            open=float(raw.open),
            high=float(raw.high),
            low=float(raw.low),
            close=float(raw.close),
            volume=float(raw.volume),
            adj_close=None,
        )
