import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from alpha_quant.domain.models import (
    Bar,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def freeze_bundle(
    output_dir: Path,
    bars: dict[str, list[Bar]],
    fundamentals: dict[str, FundamentalsSnapshot],
    earnings: list[EarningsEntry],
    insider_tx: dict[str, list[InsiderTransaction]],
    mentions: dict[str, list[MentionCount]],
    version: str = "v1",
) -> Path:
    bundle = output_dir / "fixtures" / version
    bundle.mkdir(parents=True, exist_ok=True)

    bars_dir = bundle / "bars"
    bars_dir.mkdir(exist_ok=True)
    for symbol, entries in bars.items():
        _write_table(bars_dir / f"{symbol}.parquet", _bars_to_table(entries))

    fundamentals_dir = bundle / "fundamentals"
    fundamentals_dir.mkdir(exist_ok=True)
    for symbol, entry in fundamentals.items():
        _write_table(
            fundamentals_dir / f"{symbol}.parquet",
            _fundamentals_to_table(entry),
        )

    insider_dir = bundle / "insider_tx"
    insider_dir.mkdir(exist_ok=True)
    for symbol, entries in insider_tx.items():
        _write_table(insider_dir / f"{symbol}.parquet", _tx_to_table(entries))

    mentions_dir = bundle / "mentions"
    mentions_dir.mkdir(exist_ok=True)
    for symbol, entries in mentions.items():
        _write_table(mentions_dir / f"{symbol}.parquet", _mentions_to_table(entries))

    manifest: dict[str, Any] = {
        "version": version,
        "symbols": list(bars.keys()),
        "files": {},
    }
    for p in sorted(bundle.rglob("*.parquet")):
        rel = p.relative_to(bundle)
        manifest["files"][str(rel)] = _hash_file(p)

    manifest_path = bundle / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return bundle


def _write_table(path: Path, table: pa.Table) -> None:
    pq.write_table(table, path, compression="zstd")


def _bars_to_table(bars: list[Bar]) -> pa.Table:
    return pa.table(
        {
            "symbol": [b.symbol for b in bars],
            "date": [b.date.isoformat() for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
            "adj_close": [b.adj_close for b in bars],
        }
    )


def _fundamentals_to_table(entry: FundamentalsSnapshot) -> pa.Table:
    return pa.table(
        {
            "symbol": [entry.symbol],
            "as_of_date": [entry.as_of_date.isoformat()],
            "market_cap": [entry.market_cap],
            "pe_ratio": [entry.pe_ratio],
            "eps_ttm": [entry.eps_ttm],
            "dividend_yield": [entry.dividend_yield],
            "sector": [entry.sector],
            "industry": [entry.industry],
        }
    )


def _tx_to_table(tx: list[InsiderTransaction]) -> pa.Table:
    return pa.table(
        {
            "symbol": [t.symbol for t in tx],
            "filing_date": [t.filing_date.isoformat() if t.filing_date else None for t in tx],
            "transaction_date": [
                t.transaction_date.isoformat() if t.transaction_date else None for t in tx
            ],
            "owner": [t.owner for t in tx],
            "title": [t.title for t in tx],
            "transaction_type": [t.transaction_type for t in tx],
            "shares_traded": [t.shares_traded for t in tx],
            "price": [t.price for t in tx],
            "shares_held": [t.shares_held for t in tx],
        }
    )


def _mentions_to_table(mentions: list[MentionCount]) -> pa.Table:
    return pa.table(
        {
            "symbol": [m.symbol for m in mentions],
            "date": [m.mention_date.isoformat() for m in mentions],
            "source": [m.source for m in mentions],
            "count": [m.count for m in mentions],
        }
    )
