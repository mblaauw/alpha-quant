from __future__ import annotations

from datetime import date, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import Any, override

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


class InProcessLakeGateway(LakeGateway):
    """Alpha-Lake library adapter.

    Alpha-Lake is developed in parallel, so imports stay behind this adapter
    boundary and are resolved at runtime instead of leaking into ports/domain.
    """

    def __init__(self, config_path: str | Path, price_mode: str = "split_adjusted") -> None:
        try:
            config_mod = import_module("alpha_lake.config")
            catalog_mod = import_module("alpha_lake.catalog")
        except ModuleNotFoundError as exc:
            if exc.name == "alpha_lake":
                raise ModuleNotFoundError(
                    "alpha_lake is not available. "
                    "Ensure the alpha-lake Docker container is running and accessible "
                    "via lake.base_url, or use lake.mode='fixture' for fixture-based operation."
                ) from exc
            raise
        cfg = config_mod.load_config(str(config_path))
        self._con = catalog_mod.connect(cfg)
        self._snapshot_id: str | None = None
        self._price_mode = price_mode

    @override
    def pin_snapshot(self, snapshot_id: str | None) -> None:
        self._snapshot_id = snapshot_id or None

    @override
    def dataset_health(self) -> dict[str, object]:
        catalog_mod = import_module("alpha_lake.catalog")
        health = catalog_mod.catalog_health(self._con)
        datasets = {}
        for name in (
            "lake_bars",
            "fundamentals",
            "earnings_calendar",
            "insider_tx",
            "attention_metrics",
        ):
            datasets[name] = catalog_mod.dataset_health(self._con, name)
        return {**health, "datasets": datasets, "snapshot_id": self._snapshot_id}

    @override
    def bars(
        self,
        symbol: str,
        start: date,
        end: date,
        as_of: datetime,
        price_mode: str = "split_adjusted",
    ) -> list[Bar]:
        sec_id = self._resolve(symbol, as_of)
        if sec_id is None:
            return []
        serving = import_module("alpha_lake.serving")
        frame = serving.read_bars_adjusted(
            self._con,
            [sec_id],
            as_of,
            start_date=start,
            end_date=end,
            price_mode=price_mode or self._price_mode,
            snapshot_id=self._snapshot_id,
        )
        return [self._bar(row, symbol) for row in self._rows(frame)]

    @override
    def latest_bar(self, symbol: str, as_of: datetime) -> Bar | None:
        start = as_of.date() - timedelta(days=10)
        bars = self.bars(symbol, start, as_of.date(), as_of, price_mode=self._price_mode)
        return bars[-1] if bars else None

    @override
    def trading_calendar(self, start: date, end: date) -> list[TradingDay]:
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
        rows = self._pit_rows("fundamentals", symbol, as_of)
        if not rows:
            return None
        latest = max(self._effective_date(row) for row in rows)
        latest_rows = [row for row in rows if self._effective_date(row) == latest]
        values = {
            str(row.get("line_item")): self._optional_float(row.get("value")) for row in latest_rows
        }
        return FundamentalsSnapshot(
            symbol=symbol,
            as_of_date=latest,
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
            adapter="alpha_lake",
        )

    @override
    def earnings_calendar(self, start: date, end: date, as_of: datetime) -> list[EarningsEntry]:
        rows = [
            row
            for row in self._pit_rows("earnings_calendar", "", as_of)
            if start <= self._entry_date(row) <= end
        ]
        return [
            EarningsEntry(
                symbol=str(row.get("symbol") or row.get("security_id") or ""),
                date=self._entry_date(row),
                adapter="alpha_lake",
                fetch_id=row.get("source_fetch_id"),
            )
            for row in rows
        ]

    @override
    def insider_transactions(self, symbol: str, as_of: datetime) -> list[InsiderTransaction]:
        rows = self._pit_rows("insider_tx", symbol, as_of)
        return [
            InsiderTransaction(
                symbol=symbol,
                filing_date=self._effective_date(row),
                transaction_date=self._effective_date(row),
                owner=str(row.get("filer_cik") or "unknown"),
                transaction_type=str(row.get("transaction_code") or ""),
                shares_traded=float(row.get("shares") or 0.0),
                price=self._optional_float(row.get("price")),
                fetch_id=row.get("source_fetch_id"),
                adapter="alpha_lake",
            )
            for row in rows
        ]

    @override
    def mention_counts(self, symbol: str, days: int, as_of: datetime) -> list[MentionCount]:
        start = as_of.date() - timedelta(days=days - 1)
        rows = [
            row
            for row in self._pit_rows("attention_metrics", symbol, as_of)
            if start <= self._effective_date(row) <= as_of.date()
        ]
        return [
            MentionCount(
                symbol=symbol,
                mention_date=self._effective_date(row),
                source=str(row.get("source_id") or "alpha_lake_attention"),
                count=int(row.get("mention_count") or 0),
                fetch_id=row.get("source_fetch_id"),
                adapter="alpha_lake",
            )
            for row in rows
        ]

    def _resolve(self, symbol: str, as_of: datetime) -> str | None:
        security_master = import_module("alpha_lake.security_master")
        return security_master.resolve(self._con, symbol, as_of=as_of.date())

    def _pit_rows(self, dataset: str, symbol: str, as_of: datetime) -> list[dict[str, Any]]:
        sec_id = self._resolve(symbol, as_of) if symbol else None
        params: list[Any] = [as_of]
        where = ["available_at <= ?"]
        if sec_id is not None:
            where.append("security_id = ?")
            params.append(sec_id)
        query = f"SELECT * FROM {dataset} WHERE {' AND '.join(where)} ORDER BY effective_date ASC"
        try:
            result = self._con.execute(query, params)
        except Exception:
            return []
        cols = [desc[0] for desc in result.description]
        return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]

    def _rows(self, frame: Any) -> list[dict[str, Any]]:
        if hasattr(frame, "rows"):
            return list(frame.rows(named=True))
        if hasattr(frame, "to_dicts"):
            return list(frame.to_dicts())
        return []

    def _effective_date(self, row: dict[str, Any]) -> date:
        return self._date_value(row.get("effective_date") or row.get("date"))

    def _entry_date(self, row: dict[str, Any]) -> date:
        return self._date_value(row.get("report_date") or row.get("effective_date"))

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
            symbol=symbol,
            date=self._effective_date(row),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume", 0.0)),
            adj_close=self._optional_float(row.get("adj_close")),
            fetch_id=row.get("source_fetch_id"),
            adapter="alpha_lake",
        )

    def close(self) -> None:
        self._con.close()
