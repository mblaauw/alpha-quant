from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import override

import pyarrow.parquet as pq

from alpha_quant.domain.calendar import is_market_day
from alpha_quant.domain.models import Bar, Quote, TradingDay
from alpha_quant.ports.market_data import MarketData


class FixtureMarketData(MarketData):
    def __init__(self, fixture_path: Path) -> None:
        self._bars_dir = fixture_path / "bars"

    @override
    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        path = self._bars_dir / f"{symbol}.parquet"
        if not path.exists():
            return []
        table = pq.read_table(path)
        bars: list[Bar] = []
        for i in range(table.num_rows):
            row = {col: table.column(col)[i].as_py() for col in table.column_names}
            bar_date_raw = row["date"]
            if isinstance(bar_date_raw, str):
                bar_date = date.fromisoformat(bar_date_raw)
            else:
                bar_date = bar_date_raw
            if start <= bar_date <= end:
                bars.append(
                    Bar(
                        symbol=row["symbol"],
                        date=bar_date,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                        adj_close=(
                            float(row["adj_close"]) if row.get("adj_close") is not None else None
                        ),
                    )
                )
        return bars

    @override
    def latest_quote(self, symbol: str) -> Quote:
        return Quote(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            price=100.0,
            bid=99.0,
            ask=101.0,
        )

    @override
    def trading_calendar(self, start: date, end: date) -> list[TradingDay]:
        days: list[TradingDay] = []
        current = start
        while current <= end:
            days.append(
                TradingDay(
                    date=current,
                    is_open=is_market_day(current),
                    session="regular" if is_market_day(current) else None,
                )
            )
            current += timedelta(days=1)
        return days
