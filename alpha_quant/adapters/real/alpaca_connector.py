from datetime import UTC, date

import httpx
import structlog

from alpha_quant.domain.models import Bar, Quote, TradingDay
from alpha_quant.ports.market_data import MarketData

logger = structlog.get_logger()


class AlpacaConnector(MarketData):
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        *,
        base_url: str = "https://data.alpaca.markets",
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")

    def _get_stock_client(self):
        from alpaca.data.historical import StockHistoricalDataClient

        return StockHistoricalDataClient(self._api_key, self._secret_key)

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

    def trading_calendar(self, start: date, end: date) -> list[TradingDay]:
        url = f"{self._base_url}/v2/calendar"
        params: dict[str, str] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        with httpx.Client() as client:
            response = client.get(
                url,
                params=params,
                auth=(self._api_key, self._secret_key),
            )
            response.raise_for_status()
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
