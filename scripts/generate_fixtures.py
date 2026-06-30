"""Generate time-series fixture data for Alpha Lake (5 trading days × 6 symbols).

Usage: uv run python scripts/generate_fixtures.py
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path("fixtures/v1")

SYMBOLS = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]
BENCHMARKS = ["SPY"]
ALL_SYMBOLS = SYMBOLS + BENCHMARKS

START_DATE = date(2026, 1, 2)
NUM_DAYS = 5

# Base price table per symbol: [close, volume, dollar_volume]
BASE_PRICES: dict[str, list[float]] = {
    "AAPL": [155.0, 56_000_000, 2.5e9],
    "MSFT": [420.0, 22_000_000, 1.8e9],
    "GOOGL": [185.0, 18_000_000, 1.2e9],
    "NVDA": [130.0, 45_000_000, 3.1e9],
    "AMZN": [220.0, 35_000_000, 2.2e9],
    "SPY": [530.0, 40_000_000, 2.0e9],
}

# Daily return deltas for each symbol (5 days, fractional change)
RETURN_MATRIX: dict[str, list[float]] = {
    "AAPL": [0.0, 0.012, -0.025, 0.020, 0.013],
    "MSFT": [0.0, -0.005, 0.017, -0.007, 0.019],
    "GOOGL": [0.0, 0.016, -0.032, 0.022, 0.022],
    "NVDA": [0.0, 0.015, -0.030, 0.055, 0.022],
    "AMZN": [0.0, -0.009, 0.032, -0.014, 0.027],
    "SPY": [0.0, 0.004, -0.008, 0.013, 0.009],
}

# Volume multipliers per day
VOLUME_FACTORS: list[float] = [1.0, 1.1, 0.85, 1.05, 0.95]


def _market_dates(start: date, n: int) -> list[date]:
    dates: list[date] = []
    d = start
    while len(dates) < n:
        from alpha_quant.domain.calendar import is_market_day

        if is_market_day(d):
            dates.append(d)
        d = date(d.year, d.month, d.day + 1)
    return dates


def _price_series(symbol: str, dates: list[date]) -> list[dict[str, Any]]:
    base_close, base_vol, base_dvol = BASE_PRICES[symbol]
    returns = RETURN_MATRIX[symbol]
    series: list[dict[str, Any]] = []
    prev_close = base_close
    for i, d in enumerate(dates):
        ret = returns[i]
        close = round(prev_close * (1 + ret), 2)
        half_range = round(close * 0.015, 2)
        high = round(close + half_range, 2)
        low = round(close - half_range, 2)
        open_ = round(close * (1 - ret * 0.3), 2)
        volume = int(base_vol * VOLUME_FACTORS[i])
        dollar_volume = round(volume * close, 0)
        change = round(close - prev_close, 2)
        change_pct = round((close / prev_close - 1) * 100, 2)
        series.append(
            {
                "last": close,
                "high": high,
                "low": low,
                "open": open_,
                "volume": volume,
                "change": change,
                "change_pct": change_pct,
                "dollar_volume": dollar_volume,
                "latest_date": d.isoformat(),
            }
        )
        prev_close = close
    return series


def _rsi_from_returns(returns: list[float], period: int = 14) -> float | None:
    if len(returns) < period:
        return None
    gains = sum(max(r, 0) for r in returns[-period:])
    losses = sum(max(-r, 0) for r in returns[-period:])
    if losses == 0:
        return 100.0
    rs = gains / losses
    return round(100.0 - 100.0 / (1.0 + rs), 1)


def _ema(values: list[float], period: int) -> list[float]:
    multiplier = 2.0 / (period + 1)
    result: list[float] = []
    for i, v in enumerate(values):
        if i == 0:
            result.append(v)
        else:
            result.append(v * multiplier + result[-1] * (1 - multiplier))
    return result


def _readouts_for_symbol(symbol: str, prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closes = [p["last"] for p in prices]
    prev = closes[0]
    daily_returns: list[float] = []
    for c in closes:
        daily_returns.append((c - prev) / prev if prev > 0 else 0.0)
        prev = c

    rsi = _rsi_from_returns(daily_returns, 5) or 55.0

    ema_fast = _ema(closes, 3)
    ema_slow = _ema(closes, 6)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow, strict=True)]
    macd_val = macd_line[-1] if macd_line else 0.0
    macd_cross = 1 if macd_val > 0 else -1 if macd_val < 0 else 0

    vol_regime = 50.0 + (1 - daily_returns[-1] * 100) * 10 if daily_returns else 50.0

    return [
        _readout(
            "trend.directional_bias",
            "Directional Bias",
            "trend",
            60 + ord(symbol[0]) % 10,
            prices[-1]["latest_date"],
        ),  # fmt: skip
        _readout(
            "trend.regime",
            "Trend Regime",
            "trend",
            50 + ord(symbol[0]) % 10,
            prices[-1]["latest_date"],
        ),  # fmt: skip
        _readout(
            "momentum.rsi_14", "RSI(14)", "momentum", rsi, prices[-1]["latest_date"]
        ),  # fmt: skip
        _readout(
            "momentum.macd_cross", "MACD Cross", "momentum", macd_cross, prices[-1]["latest_date"]
        ),  # fmt: skip
        _readout(
            "momentum.quality",
            "Momentum Quality",
            "momentum",
            60 + int(daily_returns[-1] * 200) if daily_returns else 50,
            prices[-1]["latest_date"],
        ),  # fmt: skip
        _readout(
            "volatility.atr_percent",
            "ATR %",
            "volatility",
            1.5 + abs(daily_returns[-1]) * 10 if daily_returns else 1.5,
            prices[-1]["latest_date"],
        ),  # fmt: skip
        _readout(
            "volatility.bollinger_width",
            "Bollinger Width",
            "volatility",
            0.10 + abs(daily_returns[-1]) * 0.5 if daily_returns else 0.10,
            prices[-1]["latest_date"],
        ),  # fmt: skip
        _readout(
            "volatility.regime", "Vol Regime", "volatility", vol_regime, prices[-1]["latest_date"]
        ),  # fmt: skip
        _readout(
            "participation.rvol",
            "Relative Volume",
            "participation",
            1.0 + (symbol[0] == "S") * 0.2,
            prices[-1]["latest_date"],
        ),  # fmt: skip
        _readout(
            "relative_strength.vs_benchmark",
            "vs Benchmark",
            "relative_strength",
            0.5 + ord(symbol[0]) % 5 * 0.3,
            prices[-1]["latest_date"],
        ),  # fmt: skip
        _readout(
            "relative_strength.change_pct",
            "Change %",
            "relative_strength",
            daily_returns[-1] * 100 if daily_returns else 0,
            prices[-1]["latest_date"],
        ),  # fmt: skip
    ]


def _readout(
    readout_id: str, name: str, category: str, value: float, effective_date: str
) -> dict[str, Any]:
    return {
        "definition": {
            "readout_id": readout_id,
            "name": name,
            "category": category,
        },
        "observations": [
            {
                "effective_date": effective_date,
                "value": value,
            }
        ],
    }


def _fundamentals(symbol: str) -> list[dict[str, Any]]:
    vals: dict[str, list[float | str | None]] = {
        "AAPL": [28.5, 1.8, 0.46, 0.035],
        "MSFT": [35.0, 0.5, 0.43, 0.029],
        "GOOGL": [25.0, 0.3, 0.58, 0.040],
        "NVDA": [55.0, 0.8, 0.62, 0.018],
        "AMZN": [45.0, 1.2, 0.35, 0.022],
        "SPY": [22.0, 0.0, 0.0, 0.015],
    }
    v = vals.get(symbol, [None, None, None, None])
    return [
        {"metric_id": "pe_ttm", "name": "PE TTM", "category": "valuation", "value": v[0]},
        {
            "metric_id": "debt_to_equity_ttm",
            "name": "Debt to Equity",
            "category": "financial_health",
            "value": v[1],
        },  # fmt: skip
        {
            "metric_id": "gross_margin_ttm",
            "name": "Gross Margin TTM",
            "category": "profitability",
            "value": v[2],
        },  # fmt: skip
        {
            "metric_id": "earnings_yield_ttm",
            "name": "Earnings Yield TTM",
            "category": "valuation",
            "value": v[3],
        },  # fmt: skip
    ]


def _insider_transactions(symbol: str) -> list[dict[str, Any]]:
    if symbol == "AAPL":
        return [
            {
                "effective_date": "2026-01-03",
                "transaction_type": "Sell",
                "shares": 5000.0,
                "price": 156.0,
            },
            {
                "effective_date": "2026-01-06",
                "transaction_type": "Buy",
                "shares": 2000.0,
                "price": 153.0,
            },
        ]
    if symbol == "AMZN":
        return [
            {
                "effective_date": "2026-01-05",
                "transaction_type": "Sell",
                "shares": 10000.0,
                "price": 225.0,
            },
        ]
    return []


def _earnings_events(symbol: str, as_of: date) -> list[dict[str, Any]]:
    if symbol == "NVDA":
        earnings_date = as_of.replace(day=as_of.day + 10)
        return [
            {"effective_date": earnings_date.isoformat(), "symbol": symbol},
        ]
    return []


def _attention_mentions(symbol: str) -> list[dict[str, Any]]:
    vals: dict[str, list[int]] = {
        "AAPL": [120, 145],
        "MSFT": [85, 92],
        "GOOGL": [95, 88],
        "NVDA": [200, 350],
        "AMZN": [110, 105],
        "SPY": [50, 55],
    }
    v = vals.get(symbol, [30, 35])
    return [
        {"effective_date": "2026-01-02", "count": v[0], "source": "alpha_lake"},
        {"effective_date": "2026-01-06", "count": v[1], "source": "alpha_lake"},
    ]


def _build_bundle(
    symbol: str,
    as_of: datetime,
    snapshot_id: str,
    prices: list[dict[str, Any]],
) -> dict[str, Any]:
    as_of_date = as_of.date()
    latest_price = prices[-1] if prices else {}
    readouts = _readouts_for_symbol(symbol, prices) if prices else []
    return {
        "symbol": symbol,
        "as_of": as_of.isoformat(),
        "snapshot_id": snapshot_id,
        "categories": ["price", "technical", "fundamental", "insider", "earnings", "attention"],
        "price": latest_price,
        "readouts": readouts,
        "fundamentals": {"metrics": _fundamentals(symbol)},
        "insider_transactions": _insider_transactions(symbol),
        "earnings_events": _earnings_events(symbol, as_of_date),
        "attention_mentions": _attention_mentions(symbol),
    }


def _build_edge_bundles(date_dir: Path, snapshot_id: str) -> None:
    """Add edge-case fixtures: stale data, missing readouts, earnings blackout."""

    # Stale data bundle — old as_of, no price movement
    stale_date = date(2025, 12, 15)
    stale = {
        "symbol": "STALE",
        "as_of": datetime(
            stale_date.year, stale_date.month, stale_date.day, 14, 0, tzinfo=UTC
        ).isoformat(),
        "snapshot_id": snapshot_id,
        "categories": ["price", "technical"],
        "price": {
            "last": 100.0,
            "high": 101.0,
            "low": 99.0,
            "open": 99.5,
            "volume": 1000000,
            "change": 0.0,
            "change_pct": 0.0,
            "dollar_volume": 100000000.0,
            "latest_date": stale_date.isoformat(),
        },  # fmt: skip
        "readouts": [
            _readout("trend.regime", "Trend Regime", "trend", 30, stale_date.isoformat()),
            _readout("momentum.rsi_14", "RSI(14)", "momentum", 45, stale_date.isoformat()),
        ],
        "fundamentals": {"metrics": []},
        "insider_transactions": [],
        "earnings_events": [],
        "attention_mentions": [],
    }
    (date_dir / "stale").mkdir(parents=True, exist_ok=True)
    (date_dir / "stale" / "facts-bundle-STALE.json").write_text(json.dumps(stale, indent=2))

    # Missing readouts bundle — only 3 readouts
    missing = {
        "symbol": "POOR_DATA",
        "as_of": stale["as_of"],
        "snapshot_id": snapshot_id,
        "categories": ["price"],
        "price": {
            "last": 50.0,
            "high": 51.0,
            "low": 49.0,
            "open": 49.5,
            "volume": 500000,
            "change": 0.0,
            "change_pct": 0.0,
            "dollar_volume": 25000000.0,
            "latest_date": stale_date.isoformat(),
        },  # fmt: skip
        "readouts": [
            _readout("price.last", "Last Price", "price", 50.0, stale_date.isoformat()),
        ],
        "fundamentals": {"metrics": []},
        "insider_transactions": [],
        "earnings_events": [],
        "attention_mentions": [],
    }
    (date_dir / "stale" / "facts-bundle-POOR_DATA.json").write_text(json.dumps(missing, indent=2))

    print(f"  Edge-case bundles written to {date_dir}/stale/")


def generate() -> None:
    dates = _market_dates(START_DATE, NUM_DAYS)
    print(f"Generating {NUM_DAYS} trading days starting {START_DATE.isoformat()}")
    for d in dates:
        print(f"  Market day: {d.isoformat()}")

    # Root-level metadata
    (FIXTURE_DIR / "stale").mkdir(parents=True, exist_ok=True)

    health = {"status": "ok", "snapshots": NUM_DAYS, "latest_snapshot_id": dates[-1].isoformat()}
    (FIXTURE_DIR / "health.json").write_text(json.dumps(health, indent=2))

    contract = {
        "service": "alpha-lake",
        "api_version": "1.0",
        "minimum_alpha_quant_version": "0.3.0",
        "capabilities": [
            "pit_bars",
            "technical_indicators",
            "fundamental_metrics",
            "insider_facts",
            "earnings_events",
            "attention_metrics",
            "snapshot_reads",
        ],
    }
    (FIXTURE_DIR / "contract.json").write_text(json.dumps(contract, indent=2))

    symbols_list = [{"symbol": s, "security_id": s, "name": s} for s in ALL_SYMBOLS]
    (FIXTURE_DIR / "symbols.json").write_text(json.dumps({"symbols": symbols_list}, indent=2))

    # Price series for each symbol across all days
    price_series: dict[str, list[dict[str, Any]]] = {}
    for sym in ALL_SYMBOLS:
        price_series[sym] = _price_series(sym, dates)

    # Per-day bundles
    snapshot_id = "snap-mock-001"
    for i, d in enumerate(dates):
        date_str = d.isoformat()
        date_dir = FIXTURE_DIR / date_str
        date_dir.mkdir(parents=True, exist_ok=True)

        as_of = datetime(d.year, d.month, d.day, 14, 0, 0, tzinfo=UTC)

        for sym in ALL_SYMBOLS:
            prices_up_to = price_series[sym][: i + 1]
            bundle = _build_bundle(sym, as_of, snapshot_id, prices_up_to)
            (date_dir / f"facts-bundle-{sym}.json").write_text(json.dumps(bundle, indent=2))

        print(f"  Wrote {date_str}/ ({len(ALL_SYMBOLS)} symbols)")

    # Edge-case bundles
    _build_edge_bundles(FIXTURE_DIR, snapshot_id)

    print("Done!")


if __name__ == "__main__":
    generate()
