from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, override

import pyarrow.parquet as pq

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


class FixtureLakeGateway(LakeGateway):
    """Lake-shaped fixture reader that enforces PIT visibility in tests."""

    def __init__(self, fixture_path: Path) -> None:
        self._root = fixture_path / "lake" if (fixture_path / "lake").exists() else fixture_path
        self._snapshot_id: str | None = None
        self._cache: dict[str, list[dict[str, Any]]] = {}

    @override
    def pin_snapshot(self, snapshot_id: str | None) -> None:
        self._snapshot_id = snapshot_id or None

    @override
    def dataset_health(self) -> dict[str, object]:
        manifest = self._root / "manifest.json"
        if manifest.exists():
            return json.loads(manifest.read_text())
        datasets = sorted(path.stem for path in self._root.glob("*.parquet"))
        info: dict[str, object] = {}
        for name in datasets:
            rows = self._rows(name)
            info[name] = {
                "status": "ok" if rows else "empty",
                "row_count": len(rows),
                "latest_available_at": (
                    max(self._available_at(r) for r in rows).isoformat() if rows else None
                ),
            }
        return {
            "status": "ok" if datasets else "empty",
            "snapshot_id": self._snapshot_id,
            "datasets": info,
        }

    @override
    def bars(
        self,
        symbol: str,
        start: date,
        end: date,
        as_of: datetime,
        price_mode: str = "split_adjusted",
    ) -> list[Bar]:
        _ = price_mode
        rows = [
            row
            for row in self._visible_rows("bars", as_of)
            if self._symbol(row) == symbol and start <= self._effective_date(row) <= end
        ]
        return [self._bar(row, symbol) for row in sorted(rows, key=self._effective_date)]

    @override
    def latest_bar(self, symbol: str, as_of: datetime) -> Bar | None:
        visible = [
            row
            for row in self._visible_rows("bars", as_of)
            if self._symbol(row) == symbol and self._effective_date(row) <= as_of.date()
        ]
        if not visible:
            return None
        return self._bar(max(visible, key=self._effective_date), symbol)

    @override
    def trading_calendar(self, start: date, end: date) -> list[TradingDay]:
        rows = self._rows("trading_calendar")
        if rows:
            return [
                TradingDay(
                    date=self._date_value(row.get("date") or row.get("effective_date")),
                    is_open=bool(row.get("is_open", True)),
                    session=row.get("session") or "regular",
                )
                for row in rows
                if start <= self._date_value(row.get("date") or row.get("effective_date")) <= end
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
        rows = [
            row for row in self._visible_rows("fundamentals", as_of) if self._symbol(row) == symbol
        ]
        if not rows:
            return None
        latest_date = max(self._effective_date(row) for row in rows)
        latest_rows = [row for row in rows if self._effective_date(row) == latest_date]
        return self._fundamentals_snapshot(symbol, latest_date, latest_rows)

    @override
    def earnings_calendar(self, start: date, end: date, as_of: datetime) -> list[EarningsEntry]:
        rows = [
            row
            for row in self._visible_rows("earnings_calendar", as_of)
            if start <= self._entry_date(row) <= end
        ]
        return [self._earnings_entry(row) for row in sorted(rows, key=self._entry_date)]

    @override
    def insider_transactions(self, symbol: str, as_of: datetime) -> list[InsiderTransaction]:
        rows = [
            row for row in self._visible_rows("insider_tx", as_of) if self._symbol(row) == symbol
        ]
        return [
            self._insider_transaction(row, symbol) for row in sorted(rows, key=self._effective_date)
        ]

    @override
    def mention_counts(self, symbol: str, days: int, as_of: datetime) -> list[MentionCount]:
        start = as_of.date() - timedelta(days=days - 1)
        rows = [
            row
            for row in self._visible_rows("attention_metrics", as_of)
            if self._symbol(row) == symbol and start <= self._effective_date(row) <= as_of.date()
        ]
        return [self._mention_count(row, symbol) for row in sorted(rows, key=self._effective_date)]

    def _rows(self, dataset: str) -> list[dict[str, Any]]:
        if dataset not in self._cache:
            self._cache[dataset] = list(self._load_rows(dataset))
        return self._cache[dataset]

    def _load_rows(self, dataset: str) -> Iterable[dict[str, Any]]:
        paths: list[Path] = []
        direct = self._root / f"{dataset}.parquet"
        if direct.exists():
            paths.append(direct)
        dataset_dir = self._root / dataset
        if dataset_dir.exists():
            paths.extend(sorted(dataset_dir.rglob("*.parquet")))
        for path in paths:
            table = pq.read_table(path)
            yield from table.to_pylist()

    def _visible_rows(self, dataset: str, as_of: datetime) -> list[dict[str, Any]]:
        return [row for row in self._rows(dataset) if self._available_at(row) <= as_of]

    def _symbol(self, row: dict[str, Any]) -> str:
        return str(row.get("symbol") or row.get("ticker") or row.get("security_id") or "")

    def _effective_date(self, row: dict[str, Any]) -> date:
        return self._date_value(
            row.get("effective_date")
            or row.get("date")
            or row.get("as_of_date")
            or row.get("filing_date")
            or row.get("window_end")
        )

    def _entry_date(self, row: dict[str, Any]) -> date:
        return self._date_value(
            row.get("report_date") or row.get("date") or row.get("effective_date")
        )

    def _available_at(self, row: dict[str, Any]) -> datetime:
        raw = row.get("available_at")
        if raw is None:
            return datetime.combine(self._effective_date(row), time.max, tzinfo=UTC)
        if isinstance(raw, datetime):
            return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)

    def _date_value(self, raw: Any) -> date:
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        return date.fromisoformat(str(raw))

    def _optional_float(self, raw: Any) -> float | None:
        if raw is None:
            return None
        return float(raw)

    def _bar(self, row: dict[str, Any], symbol: str) -> Bar:
        return Bar(
            symbol=self._symbol(row) or symbol,
            date=self._effective_date(row),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume", 0.0)),
            adj_close=self._optional_float(row.get("adj_close") or row.get("adjusted_close")),
            fetch_id=row.get("source_fetch_id") or row.get("fetch_id"),
            adapter="alpha_lake_fixture",
        )

    def _fundamentals_snapshot(
        self, symbol: str, as_of_date: date, rows: list[dict[str, Any]]
    ) -> FundamentalsSnapshot:
        first = rows[0]
        wide_keys = {
            "market_cap",
            "pe_ratio",
            "eps_ttm",
            "dividend_yield",
            "sector",
            "industry",
            "operating_cash_flow",
            "total_liabilities",
            "total_debt",
            "total_equity",
            "revenue",
            "net_income",
            "accruals",
        }
        if any(key in first for key in wide_keys):
            return FundamentalsSnapshot(
                symbol=self._symbol(first) or symbol,
                as_of_date=as_of_date,
                market_cap=self._optional_float(first.get("market_cap")),
                pe_ratio=self._optional_float(first.get("pe_ratio")),
                eps_ttm=self._optional_float(first.get("eps_ttm")),
                dividend_yield=self._optional_float(first.get("dividend_yield")),
                sector=first.get("sector"),
                industry=first.get("industry"),
                operating_cash_flow=self._optional_float(first.get("operating_cash_flow")),
                total_liabilities=self._optional_float(first.get("total_liabilities")),
                total_debt=self._optional_float(first.get("total_debt")),
                total_equity=self._optional_float(first.get("total_equity")),
                revenue=self._optional_float(first.get("revenue")),
                net_income=self._optional_float(first.get("net_income")),
                accruals=self._optional_float(first.get("accruals")),
                fetch_id=first.get("source_fetch_id") or first.get("fetch_id"),
                adapter="alpha_lake_fixture",
            )

        values = {str(row.get("line_item")): self._optional_float(row.get("value")) for row in rows}
        return FundamentalsSnapshot(
            symbol=symbol,
            as_of_date=as_of_date,
            market_cap=values.get("market_cap"),
            pe_ratio=values.get("pe_ratio"),
            eps_ttm=values.get("eps_ttm"),
            dividend_yield=values.get("dividend_yield"),
            operating_cash_flow=values.get("operating_cash_flow"),
            total_liabilities=values.get("total_liabilities"),
            total_debt=values.get("total_debt"),
            total_equity=values.get("total_equity"),
            revenue=values.get("revenue"),
            net_income=values.get("net_income"),
            accruals=values.get("accruals"),
            adapter="alpha_lake_fixture",
        )

    def _earnings_entry(self, row: dict[str, Any]) -> EarningsEntry:
        return EarningsEntry(
            symbol=self._symbol(row),
            date=self._entry_date(row),
            eps_estimate=self._optional_float(row.get("eps_estimate")),
            eps_actual=self._optional_float(row.get("eps_actual")),
            revenue_estimate=self._optional_float(row.get("revenue_estimate")),
            revenue_actual=self._optional_float(row.get("revenue_actual")),
            fetch_id=row.get("source_fetch_id") or row.get("fetch_id"),
            adapter="alpha_lake_fixture",
        )

    def _insider_transaction(self, row: dict[str, Any], symbol: str) -> InsiderTransaction:
        return InsiderTransaction(
            symbol=self._symbol(row) or symbol,
            filing_date=self._effective_date(row),
            transaction_date=(
                self._date_value(row.get("transaction_date"))
                if row.get("transaction_date") is not None
                else self._effective_date(row)
            ),
            owner=str(row.get("owner") or row.get("filer_cik") or "unknown"),
            title=row.get("title"),
            transaction_type=str(row.get("transaction_type") or row.get("transaction_code") or ""),
            shares_traded=float(row.get("shares_traded") or row.get("shares") or 0.0),
            price=self._optional_float(row.get("price")),
            shares_held=self._optional_float(row.get("shares_held")),
            fetch_id=row.get("source_fetch_id") or row.get("fetch_id"),
            adapter="alpha_lake_fixture",
        )

    def _mention_count(self, row: dict[str, Any], symbol: str) -> MentionCount:
        return MentionCount(
            symbol=self._symbol(row) or symbol,
            mention_date=self._effective_date(row),
            source=str(row.get("source") or row.get("source_id") or "alpha_lake_attention"),
            count=int(row.get("count") or row.get("mention_count") or 0),
            fetch_id=row.get("source_fetch_id") or row.get("fetch_id"),
            adapter="alpha_lake_fixture",
        )
