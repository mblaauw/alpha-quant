from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from alpha_quant.application.query.shared import (
    resolve_active_book_id,
    with_uow,
)

_SECTOR_BY_SYMBOL = {
    "AAPL": "Technology",
    "AMD": "Technology",
    "AMZN": "Consumer Discretionary",
    "AVGO": "Technology",
    "GOOGL": "Communication Services",
    "JPM": "Financials",
    "META": "Communication Services",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "SPY": "Index",
    "TSLA": "Consumer Discretionary",
}


def _round(value: float, digits: int = 4) -> float:
    return round(value, digits)


def _zero_floor(value: float, digits: int = 4) -> float:
    rounded = round(value, digits)
    return 0.0 if rounded == 0 else rounded


def _pct_text(value: float) -> str:
    return f"{value * 100:.1f}%"


@dataclass(frozen=True)
class _RiskPosition:
    symbol: str
    shares: float
    market_value: float
    current_price: float
    weight: float
    sector: str
    vol: float
    beta: float
    risk_score: float


class RiskService:
    def summary(self, book_id: str | None = None) -> dict[str, object]:
        bid = UUID(book_id) if book_id else resolve_active_book_id()

        def _query(uow):
            halt = uow.store.current_halt(bid)
            active_halt = halt if halt is not None and halt.halted else None
            positions = uow.store.list_positions(bid)
            portfolio = uow.store.load_portfolio(bid)
            cash = float(portfolio.cash) if portfolio and portfolio.cash else 0.0
            total_market_value = sum(float(p.market_value or 0) for p in positions)
            equity = cash + total_market_value
            if equity <= 0:
                equity = 350_000.0

            position_rows: list[_RiskPosition] = []
            weights: list[float] = []
            for index, p in enumerate(positions):
                market_value = float(p.market_value or 0)
                current_price = float(p.current_price or 0)
                weight = market_value / equity if equity else 0.0
                weights.append(weight)
                symbol = p.symbol
                # Stable placeholder risk characteristics until the real engine lands.
                vol = 0.22 + min(index, 5) * 0.04
                beta = 0.95 + min(index, 6) * 0.12
                risk_score = max(weight * vol * beta, 0.0001)
                position_rows.append(
                    _RiskPosition(
                        symbol=symbol,
                        shares=float(p.quantity or 0),
                        market_value=market_value,
                        current_price=current_price,
                        weight=weight,
                        sector=_SECTOR_BY_SYMBOL.get(symbol, "Unclassified"),
                        vol=vol,
                        beta=beta,
                        risk_score=risk_score,
                    )
                )

            if not position_rows:
                weights = []

            gross_exposure = sum(max(weight, 0.0) for weight in weights)
            drawdown = -0.018 if positions else 0.0
            max_drawdown = -0.114 if positions else 0.0
            drawdown_limit = -0.10
            hhi_fraction = sum(weight * weight for weight in weights)
            hhi = hhi_fraction * 10_000
            effective_bets = 1 / hhi_fraction if hhi_fraction > 0 else 0.0

            risk_total = sum(row.risk_score for row in position_rows)
            component_var = []
            for row in position_rows:
                pct_of_var = row.risk_score / risk_total if risk_total > 0 else 0.0
                weight = row.weight
                component_var.append(
                    {
                        "symbol": row.symbol,
                        "pct_of_var": _round(pct_of_var),
                        "weight": _round(weight),
                        "vol": _round(row.vol, 3),
                        "beta": _round(row.beta, 2),
                        "flagged": pct_of_var > weight * 1.5 and weight > 0,
                    }
                )

            sector_totals: dict[str, float] = {}
            for row in position_rows:
                sector_totals[row.sector] = sector_totals.get(row.sector, 0.0) + row.weight
            sorted_sectors = sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
            sectors = [
                {"name": name, "pct": _round(pct), "cap": 0.70, "breach": pct > 0.70}
                for name, pct in sorted_sectors
            ]
            top_sector_name = sorted_sectors[0][0] if sorted_sectors else None
            top_sector_pct = sorted_sectors[0][1] if sorted_sectors else 0.0
            top_sector_breach = top_sector_pct > 0.70

            var_95_pct = 0.025 if positions else 0.0
            var_99_pct = 0.036 if positions else 0.0
            es_975_pct = 0.031 if positions else 0.0
            ann_vol = 0.243 if positions else 0.0
            beta = (
                sum(row.beta * row.weight for row in position_rows) / gross_exposure
                if gross_exposure > 0
                else 0.0
            )
            avg_correlation = 0.58 if len(position_rows) > 1 else 0.0
            diversification_ratio = 1.34 if len(position_rows) > 1 else 1.0 if positions else 0.0

            limit_rows = [
                (
                    "Gross exposure",
                    _pct_text(gross_exposure),
                    "cap 90%",
                    _round(gross_exposure / 0.90 if gross_exposure else 0.0, 2),
                    gross_exposure > 0.90,
                ),
                (
                    "1-day 99% VaR",
                    _pct_text(var_99_pct),
                    "budget 4.0%",
                    _round(var_99_pct / 0.04 if var_99_pct else 0.0, 2),
                    var_99_pct > 0.04,
                ),
                (
                    "Max drawdown",
                    _pct_text(abs(max_drawdown)),
                    "limit 10.0%",
                    _round(abs(max_drawdown) / abs(drawdown_limit), 2),
                    max_drawdown < drawdown_limit,
                ),
            ]
            if top_sector_name:
                limit_rows.insert(
                    0,
                    (
                        f"Sector — {top_sector_name}",
                        _pct_text(top_sector_pct),
                        "cap 70%",
                        _round(top_sector_pct / 0.70, 2),
                        top_sector_breach,
                    ),
                )
            limits = [
                {
                    "name": name,
                    "current": current,
                    "limit": limit,
                    "utilization": utilization,
                    "breach": breach,
                }
                for name, current, limit, utilization, breach in limit_rows
            ]

            events = []
            for name, current, limit, utilization, breach in limit_rows:
                if breach:
                    events.append(
                        {
                            "severity": "crit",
                            "title": f"{name} breach",
                            "at": "20:00",
                            "detail": f"{current} exceeds {limit}.",
                        }
                    )
                elif utilization >= 0.85:
                    events.append(
                        {
                            "severity": "warn",
                            "title": f"{name} near limit",
                            "at": "20:00",
                            "detail": f"{current} uses {utilization:.0%} of {limit}.",
                        }
                    )

            if not events:
                events.append(
                    {
                        "severity": "info",
                        "title": "Risk contract placeholder",
                        "at": "20:00",
                        "detail": (
                            "Risk Desk shape is live; real VaR engine is tracked in "
                            "GitHub issue #612."
                        ),
                    }
                )

            halted = active_halt is not None
            critical = any(event["severity"] == "crit" for event in events)
            warnings = any(event["severity"] == "warn" for event in events)
            posture_state = "halt" if halted else "elevated" if critical or warnings else "ready"
            if active_halt is not None:
                posture_text = active_halt.details or "Manual halt is active for this book."
            elif critical and top_sector_name and top_sector_breach:
                posture_text = (
                    f"{_pct_text(top_sector_pct)} {top_sector_name} exposure exceeds "
                    "the 70% cap; new entries should remain blocked."
                )
            elif warnings:
                posture_text = (
                    "One or more risk limits are near their threshold; review before adding risk."
                )
            else:
                posture_text = "Risk posture is ready; no placeholder limit breaches are active."

            near_stop = []
            for p in positions:
                stop = float(p.stop_price) if p.stop_price else None
                current = float(p.current_price) if p.current_price else None
                if stop and current and stop > 0:
                    dist = (current - stop) / current * 100
                    if dist < 5:
                        near_stop.append(
                            {
                                "symbol": p.symbol,
                                "dist_to_stop_pct": round(dist, 2),
                            }
                        )
            scenario_tech = -0.15 * sector_totals.get("Technology", 0.0) * equity
            return {
                "as_of": datetime.now(UTC).isoformat(),
                "equity": round(equity, 2),
                "halted": halted,
                "halt": {
                    "reason": active_halt.reason.value if active_halt.reason else None,
                    "details": active_halt.details,
                    "halted_at": str(active_halt.halted_at) if active_halt.halted_at else None,
                }
                if active_halt
                else None,
                "posture": {
                    "state": posture_state,
                    "text": posture_text,
                },
                "headline": {
                    "var_1d_99_pct": var_99_pct,
                    "var_1d_99_usd": round(equity * var_99_pct, 2),
                    "es_975_pct": es_975_pct,
                    "es_975_usd": round(equity * es_975_pct, 2),
                    "ann_vol": ann_vol,
                    "beta": _round(beta, 2),
                    "drawdown": drawdown,
                    "max_drawdown": max_drawdown,
                    "drawdown_limit": drawdown_limit,
                    "gross_exposure": _round(gross_exposure),
                    "gross_cap": 0.90,
                    "effective_bets": _round(effective_bets, 1),
                    "hhi": round(hhi),
                },
                "var": {
                    "horizon_days": 1,
                    "levels": {
                        "p95": {
                            "pct": var_95_pct,
                            "usd": round(equity * var_95_pct, 2),
                            "parametric": var_95_pct,
                            "historical": _round(var_95_pct * 1.08),
                            "monte_carlo": _round(var_95_pct * 1.04),
                        },
                        "p99": {
                            "pct": var_99_pct,
                            "usd": round(equity * var_99_pct, 2),
                            "parametric": var_99_pct,
                            "historical": _round(var_99_pct * 1.08),
                            "monte_carlo": _round(var_99_pct * 1.03),
                        },
                        "es975": {
                            "pct": es_975_pct,
                            "usd": round(equity * es_975_pct, 2),
                            "parametric": es_975_pct,
                            "historical": _round(es_975_pct * 1.10),
                            "monte_carlo": _round(es_975_pct * 1.03),
                        },
                    },
                    "method_params": {
                        "ewma_lambda": 0.94,
                        "hist_window_days": 500,
                        "mc_paths": 10000,
                        "placeholder": True,
                    },
                },
                "component_var": component_var,
                "scenarios": [
                    {
                        "name": "2008 Global Financial Crisis",
                        "kind": "historical",
                        "pnl_usd": _zero_floor(-0.337 * gross_exposure * equity, 2),
                        "pnl_pct": _zero_floor(-0.337 * gross_exposure),
                    },
                    {
                        "name": "COVID shock",
                        "kind": "historical",
                        "pnl_usd": _zero_floor(-0.214 * gross_exposure * equity, 2),
                        "pnl_pct": _zero_floor(-0.214 * gross_exposure),
                    },
                    {
                        "name": "Technology -15%",
                        "kind": "hypothetical",
                        "pnl_usd": _zero_floor(scenario_tech, 2),
                        "pnl_pct": _zero_floor(scenario_tech / equity if equity else 0.0),
                    },
                ],
                "concentration": {
                    "effective_bets": _round(effective_bets, 1),
                    "hhi": round(hhi),
                    "avg_correlation": avg_correlation,
                    "diversification_ratio": diversification_ratio,
                    "top3_pct": _round(sum(sorted(weights, reverse=True)[:3])),
                    "sectors": sectors,
                },
                "factors": {
                    "beta": _round(beta, 2),
                    "styles": [
                        {"name": "Momentum", "tilt": 0.42 if positions else 0.0},
                        {"name": "Value-Growth", "tilt": -0.55 if positions else 0.0},
                        {"name": "Size", "tilt": -0.31 if positions else 0.0},
                        {"name": "Volatility", "tilt": 0.38 if positions else 0.0},
                        {"name": "Quality", "tilt": 0.22 if positions else 0.0},
                    ],
                },
                "liquidity": [
                    {
                        "symbol": row.symbol,
                        "adv_usd": 12_000_000_000.0,
                        "shares": row.shares,
                        "days_to_liquidate": _round(
                            (row.market_value / 12_000_000_000.0) / 0.20, 2
                        ),
                    }
                    for row in position_rows
                ],
                "limits": limits,
                "events": events,
                "positions_count": len(positions),
                "near_stop": near_stop,
                "recent_risk_events": events,
            }

        return with_uow(_query)

    def halt_state(self) -> dict[str, object]:
        bid = resolve_active_book_id()

        def _query(uow):
            halt = uow.store.current_halt(bid)
            active_halt = halt if halt is not None and halt.halted else None
            return {
                "halted": active_halt is not None,
                "halt": {
                    "reason": active_halt.reason.value if active_halt.reason else None,
                    "details": active_halt.details,
                    "halted_at": str(active_halt.halted_at) if active_halt.halted_at else None,
                }
                if active_halt
                else None,
                "recent_transitions": [],
            }

        return with_uow(_query)
