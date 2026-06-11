from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import override

import pyarrow.parquet as pq

from alpha_quant.domain.models import InsiderCluster, InsiderTransaction
from alpha_quant.ports.insider_feed import InsiderFeed


class FixtureInsiderFeed(InsiderFeed):
    def __init__(self, fixture_path: Path) -> None:
        self._insider_dir = fixture_path / "insider_tx"

    @override
    def cluster_transactions(self, symbol: str) -> list[InsiderTransaction]:
        path = self._insider_dir / f"{symbol}.parquet"
        if not path.exists():
            return []
        table = pq.read_table(path)
        transactions: list[InsiderTransaction] = []
        for i in range(table.num_rows):
            row = {col: table.column(col)[i].as_py() for col in table.column_names}
            raw_filing = row.get("filing_date")
            raw_tx = row.get("transaction_date")
            transactions.append(
                InsiderTransaction(
                    symbol=row.get("symbol", symbol),
                    filing_date=(
                        date.fromisoformat(raw_filing)
                        if isinstance(raw_filing, str)
                        else date.today()
                    ),
                    transaction_date=(
                        date.fromisoformat(raw_tx) if isinstance(raw_tx, str) else None
                    ),
                    owner=row.get("owner", ""),
                    title=row.get("title"),
                    transaction_type=row.get("transaction_type", ""),
                    shares_traded=float(row.get("shares_traded", 0)),
                    price=float(row["price"]) if row.get("price") is not None else None,
                    shares_held=(
                        float(row["shares_held"]) if row.get("shares_held") is not None else None
                    ),
                )
            )
        return transactions

    @override
    def recent_clusters(self, symbol: str) -> list[InsiderCluster]:
        _ = symbol
        return []
