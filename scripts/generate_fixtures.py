from __future__ import annotations

import json
import math
import os
from pathlib import Path

import duckdb


FIXTURE_DIR = Path("fixtures/v1")
LAKE_DIR = FIXTURE_DIR / "lake"
OUTPUT_DIR = FIXTURE_DIR


def _compute_sma(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    running_sum = 0.0
    for i, v in enumerate(values):
        running_sum += v
        if i >= period:
            running_sum -= values[i - period]
        if i + 1 >= period:
            result.append(running_sum / period)
        else:
            result.append(None)
    return result


def _compute_ema(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    multiplier = 2.0 / (period + 1)
    ema: float | None = None
    for v in values:
        if ema is None:
            ema = v
        else:
            ema = v * multiplier + ema * (1 - multiplier)
        result.append(ema)
    return result


def _compute_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    result: list[float | None] = []
    gains: list[float] = []
    losses: list[float] = []
    for i in range(len(closes)):
        if i == 0:
            gains.append(0.0)
            losses.append(0.0)
        else:
            diff = closes[i] - closes[i - 1]
            gains.append(max(0.0, diff))
            losses.append(max(0.0, -diff))
    avg_gain: float | None = None
    avg_loss: float | None = None
    for i in range(len(closes)):
        if i + 1 < period:
            result.append(None)
            continue
        if avg_gain is None:
            avg_gain = sum(gains[i - period + 1 : i + 1]) / period
            avg_loss = sum(losses[i - period + 1 : i + 1]) / period
        else:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - 100.0 / (1.0 + rs)
            result.append(rsi)
    return result


def _compute_macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    ema_fast = _compute_ema(closes, fast)
    ema_slow = _compute_ema(closes, slow)
    macd_line: list[float | None] = []
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line.append(ema_fast[i] - ema_slow[i])  # type: ignore[operator]
        else:
            macd_line.append(None)
    macd_filled = [v for v in macd_line if v is not None]
    signal_line_raw = _compute_ema(macd_filled, signal)
    signal_line: list[float | None] = [None] * (len(closes) - len(macd_filled)) + signal_line_raw
    histogram: list[float | None] = []
    for i in range(len(closes)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram.append(macd_line[i] - signal_line[i])  # type: ignore[operator]
        else:
            histogram.append(None)
    return macd_line, signal_line, histogram


def _compute_atr_pct(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> list[float | None]:
    tr_values: list[float] = []
    for i in range(len(closes)):
        if i == 0:
            tr_values.append(highs[i] - lows[i])
        else:
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            tr_values.append(tr)
    atr = _compute_ema(tr_values, period)
    for i in range(len(atr)):
        if atr[i] is not None and closes[i] > 0:
            atr[i] = atr[i] / closes[i]  # type: ignore[operator]
        else:
            atr[i] = None
    return atr


def _compute_return(closes: list[float], n: int = 63) -> list[float | None]:
    result: list[float | None] = []
    for i in range(len(closes)):
        if i >= n and closes[i - n] > 0:
            result.append(closes[i] / closes[i - n] - 1.0)
        else:
            result.append(None)
    return result


def _compute_volume_ratio(volumes: list[float], period: int = 21) -> list[float | None]:
    result: list[float | None] = []
    for i in range(len(volumes)):
        if i + 1 >= period:
            avg = sum(volumes[i - period + 1 : i + 1]) / period
            result.append(volumes[i] / avg if avg > 0 else None)
        else:
            result.append(None)
    return result


def _last_non_none(values: list[float | None]) -> float | None:
    for v in reversed(values):
        if v is not None:
            return v
    return None


def _compute_indicators(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> dict[str, list[float | None]]:
    sma_50 = _compute_sma(closes, 50)
    sma_200 = _compute_sma(closes, 200)
    rsi_14 = _compute_rsi(closes, 14)
    _, _, macd_hist = _compute_macd(closes)
    atr_pct = _compute_atr_pct(highs, lows, closes, 14)
    ret_63d = _compute_return(closes, 63)
    vol_ratio = _compute_volume_ratio(volumes, 21)
    return {
        "trend.ma_regime_50": sma_50,
        "trend.ma_regime_200": sma_200,
        "momentum.rsi_14": rsi_14,
        "trend.macd_histogram": macd_hist,
        "volatility.atr_pct_14": atr_pct,
        "momentum.return_63d": ret_63d,
        "liquidity.volume_ratio_21": vol_ratio,
    }


def _read_manifest() -> dict:
    with open(LAKE_DIR / "manifest.json") as f:
        return json.load(f)


def _read_bars(con: duckdb.DuckDBPyConnection) -> dict[str, list[dict]]:
    rows = con.execute(
        """
        SELECT symbol, effective_date, open, high, low, close, volume, adj_close
        FROM 'fixtures/v1/lake/bars.parquet'
        ORDER BY symbol, effective_date
        """
    ).fetchall()
    columns = ["symbol", "effective_date", "open", "high", "low", "close", "volume", "adj_close"]
    symbols: dict[str, list[dict]] = {}
    for row in rows:
        rec = dict(zip(columns, row))
        sym = rec["symbol"]
        rec["effective_date"] = str(rec["effective_date"])
        if rec["adj_close"] is not None:
            rec["adj_close"] = float(rec["adj_close"])
        if sym not in symbols:
            symbols[sym] = []
        symbols[sym].append(rec)
    return symbols


def _read_fundamentals(con: duckdb.DuckDBPyConnection) -> dict[str, list[dict]]:
    rows = con.execute(
        """
        SELECT symbol, effective_date, market_cap, pe_ratio, eps_ttm,
               dividend_yield, sector, industry,
               total_debt, total_equity, net_income, accruals
        FROM 'fixtures/v1/lake/fundamentals.parquet'
        ORDER BY symbol, effective_date
        """
    ).fetchall()
    symbols: dict[str, list[dict]] = {}
    for row in rows:
        sym, eff_date, mc, pe, eps, div_yield, sector, industry, debt, equity, net_inc, accruals = (
            row
        )
        metrics = []
        if mc is not None:
            metrics.append(
                {
                    "metric_id": "fundamentals.valuation.market_cap",
                    "name": "Market Cap",
                    "category": "valuation",
                    "value": float(mc),
                }
            )
        if pe is not None:
            metrics.append(
                {
                    "metric_id": "fundamentals.valuation.pe_ttm",
                    "name": "PE TTM",
                    "category": "valuation",
                    "value": float(pe),
                }
            )
        if eps is not None:
            metrics.append(
                {
                    "metric_id": "fundamentals.valuation.earnings_yield_ttm",
                    "name": "Earnings Yield TTM",
                    "category": "valuation",
                    "value": float(eps),
                }
            )
        if div_yield is not None:
            metrics.append(
                {
                    "metric_id": "fundamentals.valuation.dividend_yield",
                    "name": "Dividend Yield",
                    "category": "valuation",
                    "value": float(div_yield),
                }
            )
        if debt is not None and equity is not None and equity != 0:
            metrics.append(
                {
                    "metric_id": "fundamentals.financial_health.debt_to_equity_ttm",
                    "name": "Debt to Equity",
                    "category": "financial_health",
                    "value": float(debt) / float(equity),
                }
            )
        if sector is not None:
            metrics.append(
                {
                    "metric_id": "fundamentals.profitability.gross_margin_ttm",
                    "name": "Sector",
                    "category": "profitability",
                    "value": None,
                    "state": sector,
                }
            )
        symbols.setdefault(sym, []).extend(metrics)
    return symbols


def _map_field_name(name: str) -> str:
    mapping = {
        "shares_traded": "shares",
        "mention_count": "count",
        "source_id": "source",
    }
    return mapping.get(name, name)


def _read_insider_tx(con: duckdb.DuckDBPyConnection) -> dict[str, list[dict]]:
    rows = con.execute(
        """
        SELECT symbol, effective_date, transaction_type, shares_traded, price
        FROM 'fixtures/v1/lake/insider_tx.parquet'
        ORDER BY symbol, effective_date
        """
    ).fetchall()
    symbols: dict[str, list[dict]] = {}
    for row in rows:
        sym, eff_date, tx_type, shares, price = row
        rec = {
            "effective_date": str(eff_date),
            "transaction_type": tx_type,
            "shares": float(shares) if shares is not None else None,
            "price": float(price) if price is not None else None,
        }
        symbols.setdefault(sym, []).append(rec)
    return symbols


def _read_earnings(con: duckdb.DuckDBPyConnection) -> dict[str, list[dict]]:
    rows = con.execute(
        """
        SELECT symbol, effective_date
        FROM 'fixtures/v1/lake/earnings_calendar.parquet'
        ORDER BY symbol, effective_date
        """
    ).fetchall()
    symbols: dict[str, list[dict]] = {}
    for row in rows:
        sym, eff_date = row
        rec = {
            "effective_date": str(eff_date),
            "symbol": sym,
        }
        symbols.setdefault(sym, []).append(rec)
    return symbols


def _read_attention_metrics(con: duckdb.DuckDBPyConnection) -> dict[str, list[dict]]:
    rows = con.execute(
        """
        SELECT symbol, effective_date, mention_count, source_id
        FROM 'fixtures/v1/lake/attention_metrics.parquet'
        ORDER BY symbol, effective_date
        """
    ).fetchall()
    symbols: dict[str, list[dict]] = {}
    for row in rows:
        sym, eff_date, count, source = row
        rec = {
            "effective_date": str(eff_date),
            "count": int(count) if count is not None else 0,
            "source": source or "alpha_lake",
        }
        symbols.setdefault(sym, []).append(rec)
    return symbols


def _build_symbol_panel(
    sym: str,
    bars: list[dict],
    fundamentals: list[dict],
    insider_tx: list[dict],
    earnings: list[dict],
    attention: list[dict],
) -> dict:
    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    volumes = [b["volume"] for b in bars]
    indicators = _compute_indicators(closes, highs, lows, volumes)

    bar_obs: list[dict] = []
    for b in bars:
        bar_obs.append(
            {
                "effective_date": b["effective_date"],
                "open": b["open"],
                "high": b["high"],
                "low": b["low"],
                "close": b["close"],
                "volume": b["volume"],
                "adj_close": b["adj_close"],
            }
        )

    panel: dict = {
        "symbol": sym,
        "bars": bar_obs,
        "indicators": indicators,
        "fundamentals": fundamentals,
        "insider_transactions": insider_tx,
        "earnings_events": earnings,
        "attention_mentions": attention,
    }
    return panel


def generate() -> None:
    manifest = _read_manifest()
    symbols = manifest["symbols"]
    snapshot_id = manifest["snapshot_id"]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    con = duckdb.connect()

    bars_data = _read_bars(con)
    fundamentals_data = _read_fundamentals(con)
    insider_data = _read_insider_tx(con)
    earnings_data = _read_earnings(con)
    attention_data = _read_attention_metrics(con)

    panels: dict[str, dict] = {}
    for sym in symbols:
        sym_bars = bars_data.get(sym, [])
        sym_fundamentals = fundamentals_data.get(sym, [])
        sym_insider = insider_data.get(sym, [])
        sym_earnings = earnings_data.get(sym, [])
        sym_attention = attention_data.get(sym, [])

        if not sym_bars:
            continue

        panels[sym] = _build_symbol_panel(
            sym, sym_bars, sym_fundamentals, sym_insider, sym_earnings, sym_attention
        )

    max_date = max(bars_data[sym][-1]["effective_date"] for sym in panels)

    decision_panel = {
        "as_of": f"{max_date}T20:00:00+00:00",
        "snapshot_id": snapshot_id,
        "symbols": list(panels.keys()),
        "panels": panels,
    }

    with open(OUTPUT_DIR / "decision-panel.json", "w") as f:
        json.dump(decision_panel, f, indent=2, default=str)
    print(f"Wrote decision-panel.json ({len(panels)} symbols)")

    health = {
        "status": "ok",
        "snapshots": 1,
        "latest_snapshot_id": snapshot_id,
    }
    with open(OUTPUT_DIR / "health.json", "w") as f:
        json.dump(health, f, indent=2)
    print("Wrote health.json")

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
    with open(OUTPUT_DIR / "contract.json", "w") as f:
        json.dump(contract, f, indent=2)
    print("Wrote contract.json")

    members = [{"symbol": sym, "security_id": sym, "name": sym} for sym in symbols]
    universe = {"as_of": max_date, "members": members}
    with open(OUTPUT_DIR / "universe.json", "w") as f:
        json.dump(universe, f, indent=2, default=str)
    print("Wrote universe.json")

    con.close()
    print("Done!")


if __name__ == "__main__":
    generate()
