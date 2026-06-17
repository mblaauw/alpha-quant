from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, override

import duckdb

from app.store.canonical import (
    latest_date,
    load_corp_actions,
    load_earnings,
    read_bars,
    read_fundamentals,
    read_insider_transactions,
    read_mentions,
    write_dataset,
)
from domain.models import (
    Bar,
    CorporateAction,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
)
from ports.store import BarStore


class BarStoreMixin(BarStore):
    _analytical: duckdb.DuckDBPyConnection
    _base: Path

    def _write_dataset(self, models: list[Any], dataset: str) -> None:
        write_dataset(self._analytical, self._base, models, dataset)

    def _write_bars(self, bars: list[Bar]) -> None:
        self._write_dataset(bars, "bars")

    def _write_fundamentals(self, snapshots: list[FundamentalsSnapshot]) -> None:
        self._write_dataset(snapshots, "fundamentals")

    def _write_insider_transactions(self, transactions: list[InsiderTransaction]) -> None:
        self._write_dataset(transactions, "insider_transactions")

    def _write_mentions(self, mentions: list[MentionCount]) -> None:
        self._write_dataset(mentions, "mentions")

    def _read_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return read_bars(self._analytical, self._base, symbol, start, end)

    def _canonical_path(self, dataset: str) -> Path:
        return self._base / "canonical" / dataset

    @override
    def save_bars(self, symbol: str, bars: list[Bar]) -> None:
        self._write_bars(bars)

    @override
    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return self._read_bars(symbol, start, end)

    @override
    def latest_bar_date(self, symbol: str) -> date | None:
        return latest_date(self._analytical, self._base, "bars", symbol, "date")

    @override
    def latest_fundamentals_date(self, symbol: str) -> date | None:
        return latest_date(self._analytical, self._base, "fundamentals", symbol, "as_of_date")

    @override
    def save_corp_actions(self, symbol: str, actions: list[CorporateAction]) -> None:
        self._write_dataset(actions, "corp_actions")

    @override
    def load_corp_actions(self, symbol: str) -> list[CorporateAction]:
        return load_corp_actions(self._analytical, self._base, symbol)

    @override
    def save_earnings(self, symbol: str, entries: list[EarningsEntry]) -> None:
        self._write_dataset(entries, "earnings")

    @override
    def load_earnings(self, symbol: str) -> list[EarningsEntry]:
        return load_earnings(self._analytical, self._base, symbol)

    @override
    def load_fundamentals(self, symbol: str) -> list[FundamentalsSnapshot]:
        return read_fundamentals(self._analytical, self._base, symbol)

    @override
    def load_insider_transactions(self, symbol: str) -> list[InsiderTransaction]:
        return read_insider_transactions(self._analytical, self._base, symbol)

    @override
    def load_mentions(self, symbol: str) -> list[MentionCount]:
        return read_mentions(self._analytical, self._base, symbol)

    @override
    def save_fundamentals(self, symbol: str, snapshots: list[FundamentalsSnapshot]) -> None:
        self._write_fundamentals(snapshots)

    @override
    def save_insider_transactions(self, symbol: str, txns: list[InsiderTransaction]) -> None:
        self._write_insider_transactions(txns)

    @override
    def save_mentions(self, symbol: str, mentions: list[MentionCount]) -> None:
        self._write_mentions(mentions)
