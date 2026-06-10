from datetime import date
from datetime import date as date_type

from alpha_quant.domain.models import Bar, Quote, TradingDay
from alpha_quant.ports.market_data import MarketData


class FixtureMarketData(MarketData):
    def __init__(
        self,
        bars: dict[str, list[Bar]] | None = None,
        quotes: dict[str, Quote] | None = None,
    ) -> None:
        self._bars: dict[str, list[Bar]] = bars or {}
        self._quotes: dict[str, Quote] = quotes or {}
        self._calendar: list[TradingDay] = []

    def seed_bars(self, symbol: str, bars: list[Bar]) -> None:
        self._bars[symbol] = bars

    def seed_quote(self, symbol: str, quote: Quote) -> None:
        self._quotes[symbol] = quote

    def seed_calendar(self, days: list[TradingDay]) -> None:
        self._calendar = days

    async def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        all_bars = self._bars.get(symbol)
        if all_bars is None:
            msg = f"No fixture data for symbol: {symbol}"
            raise ValueError(msg)
        return [b for b in all_bars if start <= b.date <= end]

    async def latest_quote(self, symbol: str) -> Quote:
        if symbol not in self._quotes:
            msg = f"No fixture quote for symbol: {symbol}"
            raise ValueError(msg)
        return self._quotes[symbol]

    async def trading_calendar(self, start: date_type, end: date_type) -> list[TradingDay]:
        return [d for d in self._calendar if start <= d.date <= end]
