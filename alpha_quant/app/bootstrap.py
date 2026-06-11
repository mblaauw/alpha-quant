from datetime import date, timedelta
from pathlib import Path
from typing import Any

from alpha_quant.app.config import AppConfig
from alpha_quant.app.fixtures import freeze_bundle
from alpha_quant.app.vault import write_blob
from alpha_quant.domain.models import (
    Bar,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
)


def _generate_bars(symbol: str, start: date, end: date) -> list[Bar]:
    bars: list[Bar] = []
    price = 100.0
    current = start
    while current <= end:
        if current.weekday() < 5:
            bars.append(
                Bar(
                    symbol=symbol,
                    date=current,
                    open=price,
                    high=price * 1.02,
                    low=price * 0.98,
                    close=price * (1 + (hash(f"{symbol}-{current}") % 21 - 10) / 500),
                    volume=1_000_000 + hash(f"v-{symbol}-{current}") % 500_000,
                )
            )
            price = bars[-1].close
        current += timedelta(days=1)
    return bars


def _generate_fundamentals(symbol: str) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        symbol=symbol,
        as_of_date=date.today(),
        market_cap=50_000_000_000 + hash(symbol) % 2_000_000_000_000,
        pe_ratio=15.0 + hash(symbol) % 30,
        eps_ttm=2.0 + hash(symbol) % 10,
        dividend_yield=0.5 + hash(symbol) % 3,
        sector="Technology",
        industry="Software",
    )


def _generate_earnings(symbol: str, years: int) -> list[EarningsEntry]:
    entries: list[EarningsEntry] = []
    for y in range(date.today().year - years, date.today().year + 1):
        for q in range(1, 5):
            entries.append(
                EarningsEntry(
                    symbol=symbol,
                    date=date(y, q * 3, 15),
                    eps_estimate=1.0 + hash(f"e-{symbol}-{y}-{q}") % 200 / 100,
                    eps_actual=1.0 + hash(f"a-{symbol}-{y}-{q}") % 200 / 100,
                )
            )
    return entries


def _generate_insider_tx(symbol: str) -> list[InsiderTransaction]:
    return [
        InsiderTransaction(
            symbol=symbol,
            filing_date=date.today() - timedelta(days=d),
            transaction_date=date.today() - timedelta(days=d + 2),
            owner=f"exec_{i % 5 + 1}",
            title="Officer",
            transaction_type="Buy" if i % 3 != 0 else "Sell",
            shares_traded=1_000 + hash(f"i-{symbol}-{i}") % 10_000,
            price=100.0,
            shares_held=10_000 + hash(f"h-{symbol}-{i}") % 100_000,
        )
        for i, d in enumerate(range(5, 365, 30))
    ]


def _generate_mentions(symbol: str) -> list[MentionCount]:
    return [
        MentionCount(
            symbol=symbol,
            date=date.today() - timedelta(days=d),
            source="reddit",
            count=10 + hash(f"m-{symbol}-{d}") % 200,
        )
        for d in range(30)
    ]


def run_bootstrap(
    config: AppConfig,
    vault_base: Path,
    fixture_base: Path,
    fixture_only: bool = False,
) -> dict[str, Any]:
    cfg = config.bootstrap
    today = date.today()
    start = date(today.year - cfg.history_years, today.month, today.day)

    all_symbols = list(cfg.symbols) + list(cfg.include_benchmarks)
    result: dict[str, Any] = {"symbols": all_symbols, "fixture_only": fixture_only}

    all_bars: dict[str, list[Bar]] = {}
    all_fundamentals: dict[str, FundamentalsSnapshot] = {}
    all_earnings: list[EarningsEntry] = []
    all_insider: dict[str, list[InsiderTransaction]] = {}
    all_mentions: dict[str, list[MentionCount]] = {}

    for symbol in all_symbols:
        bars = _generate_bars(symbol, start, today)
        all_bars[symbol] = bars
        all_fundamentals[symbol] = _generate_fundamentals(symbol)
        all_earnings.extend(_generate_earnings(symbol, cfg.history_years))
        all_insider[symbol] = _generate_insider_tx(symbol)
        all_mentions[symbol] = _generate_mentions(symbol)

        if not fixture_only:
            for bar in bars:
                write_blob(
                    vault_base,
                    "eodhd",
                    bar.date,
                    "bars",
                    symbol,
                    bar.model_dump_json().encode(),
                )

    bundle = freeze_bundle(
        output_dir=fixture_base,
        bars=all_bars,
        fundamentals=all_fundamentals,
        earnings=all_earnings,
        insider_tx=all_insider,
        mentions=all_mentions,
    )

    result["bundle_path"] = str(bundle)
    result["total_bars"] = sum(len(v) for v in all_bars.values())
    result["symbols_processed"] = len(all_symbols)
    return result
