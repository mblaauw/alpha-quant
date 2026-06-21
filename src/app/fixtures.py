from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from domain.models import (
    Bar,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _available_at(dt: date) -> datetime:
    return datetime.combine(dt, time.max, tzinfo=UTC) + timedelta(days=1)


def _bars_table(bars: dict[str, list[Bar]]) -> pa.Table:
    rows: list[dict[str, Any]] = []
    for symbol, entries in bars.items():
        for b in entries:
            rows.append(
                {
                    "symbol": symbol,
                    "effective_date": b.date,
                    "available_at": _available_at(b.date),
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "adj_close": b.adj_close,
                    "source_fetch_id": b.fetch_id,
                }
            )
    return pa.Table.from_pylist(rows)


def _fundamentals_table(fundamentals: dict[str, FundamentalsSnapshot]) -> pa.Table:
    rows: list[dict[str, Any]] = []
    for symbol, entry in fundamentals.items():
        rows.append(
            {
                "symbol": symbol,
                "effective_date": entry.as_of_date,
                "available_at": _available_at(entry.as_of_date),
                "market_cap": entry.market_cap,
                "pe_ratio": entry.pe_ratio,
                "eps_ttm": entry.eps_ttm,
                "dividend_yield": entry.dividend_yield,
                "sector": entry.sector,
                "industry": entry.industry,
                "operating_cash_flow": entry.operating_cash_flow,
                "total_liabilities": entry.total_liabilities,
                "total_debt": entry.total_debt,
                "total_equity": entry.total_equity,
                "revenue": entry.revenue,
                "net_income": entry.net_income,
                "accruals": entry.accruals,
                "source_fetch_id": entry.fetch_id,
            }
        )
    return pa.Table.from_pylist(rows)


def _earnings_table(earnings: list[EarningsEntry]) -> pa.Table:
    rows: list[dict[str, Any]] = []
    for entry in earnings:
        rows.append(
            {
                "symbol": entry.symbol,
                "effective_date": entry.date,
                "report_date": entry.date,
                "available_at": _available_at(entry.date),
                "eps_estimate": entry.eps_estimate,
                "eps_actual": entry.eps_actual,
                "revenue_estimate": entry.revenue_estimate,
                "revenue_actual": entry.revenue_actual,
                "source_fetch_id": entry.fetch_id,
            }
        )
    return pa.Table.from_pylist(rows)


def _insider_table(insider_tx: dict[str, list[InsiderTransaction]]) -> pa.Table:
    rows: list[dict[str, Any]] = []
    for symbol, txns in insider_tx.items():
        for t in txns:
            rows.append(
                {
                    "symbol": symbol,
                    "effective_date": t.filing_date or t.transaction_date,
                    "available_at": _available_at(
                        t.filing_date or t.transaction_date or date.today()
                    ),
                    "owner": t.owner,
                    "transaction_type": t.transaction_type,
                    "shares_traded": t.shares_traded,
                    "price": t.price,
                    "shares_held": t.shares_held,
                    "source_fetch_id": t.fetch_id,
                }
            )
    return pa.Table.from_pylist(rows)


def _mentions_table(mentions: dict[str, list[MentionCount]]) -> pa.Table:
    rows: list[dict[str, Any]] = []
    for symbol, entries in mentions.items():
        for m in entries:
            rows.append(
                {
                    "symbol": symbol,
                    "effective_date": m.mention_date,
                    "available_at": _available_at(m.mention_date),
                    "mention_count": m.count,
                    "source_id": m.source,
                    "source_fetch_id": m.fetch_id,
                }
            )
    return pa.Table.from_pylist(rows)


def freeze_bundle(
    output_dir: Path,
    bars: dict[str, list[Bar]],
    fundamentals: dict[str, FundamentalsSnapshot],
    earnings: list[EarningsEntry],
    insider_tx: dict[str, list[InsiderTransaction]],
    mentions: dict[str, list[MentionCount]],
    version: str = "v1",
) -> Path:
    bundle = output_dir / "fixtures" / version / "lake"
    bundle.mkdir(parents=True, exist_ok=True)

    pq.write_table(_bars_table(bars), bundle / "bars.parquet", compression="zstd")
    pq.write_table(
        _fundamentals_table(fundamentals), bundle / "fundamentals.parquet", compression="zstd"
    )
    pq.write_table(
        _earnings_table(earnings), bundle / "earnings_calendar.parquet", compression="zstd"
    )
    pq.write_table(_insider_table(insider_tx), bundle / "insider_tx.parquet", compression="zstd")
    pq.write_table(
        _mentions_table(mentions), bundle / "attention_metrics.parquet", compression="zstd"
    )

    manifest: dict[str, Any] = {
        "version": version,
        "symbols": list(bars.keys()),
        "snapshot_id": hashlib.sha256(str(datetime.now(UTC)).encode()).hexdigest()[:16],
        "files": {},
    }
    for p in sorted(bundle.rglob("*.parquet")):
        rel = p.relative_to(bundle)
        manifest["files"][str(rel)] = _hash_file(p)

    manifest_path = bundle / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return bundle
