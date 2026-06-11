from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import override

import pyarrow.parquet as pq

from alpha_quant.domain.models import EarningsEntry, FundamentalsSnapshot
from alpha_quant.ports.fundamentals import Fundamentals


class FixtureFundamentals(Fundamentals):
    def __init__(self, fixture_path: Path) -> None:
        self._fundamentals_dir = fixture_path / "fundamentals"
        self._earnings_dir = fixture_path / "earnings"

    @override
    def snapshot(self, symbol: str) -> FundamentalsSnapshot:
        path = self._fundamentals_dir / f"{symbol}.parquet"
        if not path.exists():
            return FundamentalsSnapshot(
                symbol=symbol,
                as_of_date=date.today(),
            )
        table = pq.read_table(path)
        if table.num_rows == 0:
            return FundamentalsSnapshot(symbol=symbol, as_of_date=date.today())
        row = {col: table.column(col)[0].as_py() for col in table.column_names}
        as_of_raw = row.get("as_of_date")
        if isinstance(as_of_raw, str):
            as_of = date.fromisoformat(as_of_raw)
        else:
            as_of = as_of_raw or date.today()
        return FundamentalsSnapshot(
            symbol=row.get("symbol", symbol),
            as_of_date=as_of,
            market_cap=row.get("market_cap"),
            pe_ratio=row.get("pe_ratio"),
            eps_ttm=row.get("eps_ttm"),
            dividend_yield=row.get("dividend_yield"),
            sector=row.get("sector"),
            industry=row.get("industry"),
        )

    @override
    def earnings_calendar(self, start: date, end: date) -> list[EarningsEntry]:
        if not self._earnings_dir.exists():
            return []
        entries: list[EarningsEntry] = []
        for path in self._earnings_dir.glob("*.parquet"):
            table = pq.read_table(path)
            for i in range(table.num_rows):
                row = {col: table.column(col)[i].as_py() for col in table.column_names}
                entries.append(
                    EarningsEntry(
                        symbol=row.get("symbol", ""),
                        date=row.get("date", date.today()),
                        eps_estimate=row.get("eps_estimate"),
                        eps_actual=row.get("eps_actual"),
                        revenue_estimate=row.get("revenue_estimate"),
                        revenue_actual=row.get("revenue_actual"),
                    )
                )
        return entries
