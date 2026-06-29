"""Deterministic scorecard engine — converts Alpha-Lake facts into scored components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from statistics import mean, stdev

import structlog

from alpha_quant.contracts.alpha_lake import FactsBundle, FundamentalMetric
from alpha_quant.domain.scorecard import (
    ComponentState,
    Recommendation,
    Scorecard,
    ScorecardComponent,
)

logger = structlog.get_logger()


@dataclass
class PositionContext:
    symbol: str = ""
    quantity: float = 0.0
    avg_cost: float = 0.0
    current_price: float | None = None
    stop_price: float | None = None
    market_value: float | None = None
    unrealized_pl: float | None = None


@dataclass
class PortfolioContext:
    equity: float = 0.0
    cash: float = 0.0
    regime: str = "RISK_ON"
    positions: dict[str, PositionContext] = field(default_factory=dict)
    max_positions: int = 10
    max_position_pct: float = 0.25
    discovery_symbols: list[str] = field(default_factory=list)


_RECOMMENDATION_THRESHOLDS: list[tuple[float, Recommendation, Recommendation]] = [
    (75.0, Recommendation.add, Recommendation.consider_entry),
    (55.0, Recommendation.hold, Recommendation.watch),
    (35.0, Recommendation.do_nothing, Recommendation.do_nothing),
]

_COMPONENT_WEIGHTS: dict[str, float] = {
    "technical_trend": 0.15,
    "momentum": 0.12,
    "volatility": 0.08,
    "participation": 0.06,
    "relative_strength": 0.10,
    "fundamentals": 0.12,
    "event_risk": 0.08,
    "insider_activity": 0.06,
    "attention_crowding": 0.05,
    "portfolio_fit": 0.06,
    "position_risk": 0.06,
    "cash_impact": 0.04,
    "data_quality": 0.02,
}


# Mapping from scorecard engine readout IDs to actual Alpha-Lake v2 readout IDs.
# Suffix matching handles most cases (momentum.rsi_14 → rsi_14), but some need
# explicit mapping where the last segment differs.
_READOUT_ID_MAP: dict[str, str] = {
    "atr_pct_14": "atr_percent",
    "volume_ratio_21": "rvol",
}


def _readout_value(bundle: FactsBundle, readout_id: str) -> float | None:
    """Get latest value from a readout by ID."""
    # Check explicit mapping first
    mapped = _READOUT_ID_MAP.get(readout_id)
    for item in bundle.sections.readouts:
        rid = item.definition.readout_id
        if (rid == readout_id or rid.endswith(f".{readout_id}")) and item.observations:
            return item.observations[-1].value
        if mapped and (rid == mapped or rid.endswith(f".{mapped}")) and item.observations:
            return item.observations[-1].value
    return None


def _fundamental(bundle: FactsBundle, metric_id: str) -> FundamentalMetric | None:
    for m in bundle.sections.fundamentals:
        if m.metric_id == metric_id:
            return m
    return None


def _fundamental_value(bundle: FactsBundle, metric_id: str) -> float | None:
    m = _fundamental(bundle, metric_id)
    return m.value if m else None


def _parse_date(raw: str) -> date | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):  # fmt: skip
        return None


# -- component scorers (all return 0–100) --


def _score_technical_trend(bundle: FactsBundle) -> ScorecardComponent:
    dir_bias = _readout_value(bundle, "directional_bias")
    trend_regime = _readout_value(bundle, "trend.regime")

    score = 50.0
    reasons: list[str] = []
    state = ComponentState.pass_

    if trend_regime is not None:
        if trend_regime >= 40:
            score = 70.0
            reasons.append("Strong trend regime")
        elif trend_regime >= 20:
            score = 55.0
            reasons.append("Moderate trend")
        elif trend_regime > 0:
            score = 40.0
            reasons.append("Weak trend regime (ADX)")
            state = ComponentState.warn
    else:
        reasons.append("Unknown trend")

    if dir_bias is not None:
        if dir_bias > 0:
            reasons.append("Upward bias")
            score = min(score + 10, 95)
        elif dir_bias < 0:
            reasons.append("Downward bias")
            score = max(score - 15, 10)
            state = ComponentState.warn

    return ScorecardComponent(
        name="technical_trend",
        category="technical",
        score=score,
        state=state,
        weight=_COMPONENT_WEIGHTS["technical_trend"],
        passed=score >= 20,
        reason="; ".join(reasons) if reasons else "Neutral trend",
    )


def _score_momentum(bundle: FactsBundle) -> ScorecardComponent:
    rsi_14 = _readout_value(bundle, "rsi_14")
    macd_val = _readout_value(bundle, "macd_cross")
    quality = _readout_value(bundle, "quality")

    score = 50.0
    reasons: list[str] = []
    state = ComponentState.pass_

    # Use MACD cross as a momentum proxy
    if macd_val is not None:
        if macd_val > 0:
            score = 70.0
            reasons.append("MACD positive cross")
        elif macd_val < 0:
            score = 30.0
            reasons.append("MACD negative cross")
            state = ComponentState.warn
        else:
            score = 45.0
            reasons.append("MACD neutral")
    else:
        reasons.append("MACD unavailable")

    # Momentum quality (ROC consensus)
    if quality is not None:
        if quality > 0:
            score = min(score + 15, 95)
            reasons.append("Positive momentum quality")
        elif quality < 0:
            score = max(score - 10, 10)
            reasons.append("Negative momentum quality")
            state = ComponentState.warn

    if rsi_14 is not None:
        if rsi_14 >= 70:
            score = min(score, 30.0)
            reasons.append("Overbought RSI")
            state = ComponentState.warn
        elif rsi_14 >= 60:
            score = score * 0.8 + 70 * 0.2
            reasons.append("Elevated RSI")
        elif rsi_14 <= 30:
            score = min(score, 20.0)
            reasons.append("Oversold RSI")
            state = ComponentState.warn

    return ScorecardComponent(
        name="momentum",
        category="technical",
        score=score,
        state=state,
        weight=_COMPONENT_WEIGHTS["momentum"],
        passed=score >= 20,
        reason="; ".join(reasons) if reasons else "Neutral momentum",
    )


def _score_volatility(bundle: FactsBundle) -> ScorecardComponent:
    atr_pct = _readout_value(bundle, "atr_pct_14")
    boll_width = _readout_value(bundle, "bollinger_width")
    vol_regime = _readout_value(bundle, "volatility.regime")

    reasons: list[str] = []
    score = 50.0
    state = ComponentState.pass_

    if atr_pct is not None and atr_pct > 0:
        atr_val = atr_pct * 100
        if atr_val > 4.0:
            score = 10.0
            reasons.append("Very high ATR")
            state = ComponentState.warn
        elif atr_val > 2.5:
            score = 30.0
            reasons.append("Elevated ATR")
        elif atr_val > 1.5:
            score = 60.0
            reasons.append("Moderate ATR")
        else:
            score = 85.0
            reasons.append("Low ATR")

    if boll_width is not None and not reasons:
        if boll_width > 0.5:
            score = 15.0
            reasons.append("Wide Bollinger bands")
            state = ComponentState.warn
        elif boll_width > 0.2:
            score = 40.0
            reasons.append("Moderate Bollinger width")
        elif boll_width > 0.05:
            score = 70.0
            reasons.append("Tight Bollinger bands")
        else:
            score = 85.0
            reasons.append("Squeezed Bollinger bands")

    if vol_regime is not None and not reasons:
        if vol_regime > 1.5:
            score = 20.0
            reasons.append("Elevated volatility regime")
            state = ComponentState.warn
        elif vol_regime > 1.0:
            score = 45.0
            reasons.append("Normal-high volatility")
        elif vol_regime > 0.5:
            score = 65.0
            reasons.append("Normal-low volatility")
        else:
            score = 80.0
            reasons.append("Low volatility regime")

    if not reasons:
        reasons.append("Unknown volatility")

    return ScorecardComponent(
        name="volatility",
        category="risk",
        score=score,
        state=state,
        weight=_COMPONENT_WEIGHTS["volatility"],
        reason="; ".join(reasons),
    )


def _score_participation(bundle: FactsBundle) -> ScorecardComponent:
    vol_ratio = _readout_value(bundle, "volume_ratio_21")
    if vol_ratio is None:
        return ScorecardComponent(
            name="participation",
            category="technical",
            score=50.0,
            weight=_COMPONENT_WEIGHTS["participation"],
            reason="Unknown volume participation",
        )
    if vol_ratio > 2.0:
        return ScorecardComponent(
            name="participation",
            category="technical",
            score=20.0,
            state=ComponentState.warn,
            weight=_COMPONENT_WEIGHTS["participation"],
            reason="Abnormally high volume (crowding)",
        )
    if vol_ratio > 1.5:
        return ScorecardComponent(
            name="participation",
            category="technical",
            score=60.0,
            weight=_COMPONENT_WEIGHTS["participation"],
            reason="Elevated volume",
        )
    if vol_ratio > 0.5:
        return ScorecardComponent(
            name="participation",
            category="technical",
            score=80.0,
            weight=_COMPONENT_WEIGHTS["participation"],
            reason="Healthy volume",
        )
    return ScorecardComponent(
        name="participation",
        category="technical",
        score=30.0,
        weight=_COMPONENT_WEIGHTS["participation"],
        reason="Low volume (illiquid)",
    )


def _score_relative_strength(
    bundle: FactsBundle,
    spy_bundle: FactsBundle | None,
) -> ScorecardComponent:
    # Alpha-Lake v2: use relative_strength.vs_benchmark directly
    rs_val = _readout_value(bundle, "vs_benchmark")

    if rs_val is not None:
        rel = rs_val * 100
        if rel > 5:
            return ScorecardComponent(
                name="relative_strength",
                category="technical",
                score=90.0,
                weight=_COMPONENT_WEIGHTS["relative_strength"],
                reason=f"Strong vs SPY (+{rel:.1f}%)",
            )
        if rel > 1:
            return ScorecardComponent(
                name="relative_strength",
                category="technical",
                score=70.0,
                weight=_COMPONENT_WEIGHTS["relative_strength"],
                reason=f"Above SPY ({rel:.1f}%)",
            )
        if rel > -1:
            return ScorecardComponent(
                name="relative_strength",
                category="technical",
                score=50.0,
                weight=_COMPONENT_WEIGHTS["relative_strength"],
                reason="In line with SPY",
            )
        if rel > -5:
            return ScorecardComponent(
                name="relative_strength",
                category="technical",
                score=30.0,
                weight=_COMPONENT_WEIGHTS["relative_strength"],
                reason=f"Below SPY ({rel:.1f}%)",
            )
        return ScorecardComponent(
            name="relative_strength",
            category="technical",
            score=10.0,
            state=ComponentState.warn,
            weight=_COMPONENT_WEIGHTS["relative_strength"],
            reason=f"Underperformance ({rel:.1f}%)",
        )

    # Fallback: daily change vs SPY
    sym_change = _readout_value(bundle, "change_pct")
    spy_change = _readout_value(spy_bundle, "change_pct") if spy_bundle else None
    if sym_change is not None and spy_change is not None and spy_change != 0:
        rel = (sym_change - spy_change) * 100
        if rel > 1:
            return ScorecardComponent(
                name="relative_strength",
                category="technical",
                score=70.0,
                weight=_COMPONENT_WEIGHTS["relative_strength"],
                reason=f"Outperformed SPY today ({rel:.1f}%)",
            )
        if rel > -1:
            return ScorecardComponent(
                name="relative_strength",
                category="technical",
                score=50.0,
                weight=_COMPONENT_WEIGHTS["relative_strength"],
                reason="In line with SPY today",
            )
        return ScorecardComponent(
            name="relative_strength",
            category="technical",
            score=30.0,
            weight=_COMPONENT_WEIGHTS["relative_strength"],
            reason=f"Underperformed SPY today ({rel:.1f}%)",
        )

    return ScorecardComponent(
        name="relative_strength",
        category="technical",
        score=50.0,
        weight=_COMPONENT_WEIGHTS["relative_strength"],
        reason="Relative strength not computed",
    )


def _score_fundamentals(bundle: FactsBundle) -> ScorecardComponent:
    pe = _fundamental_value(bundle, "pe_ttm")
    debt_eq = _fundamental_value(bundle, "debt_to_equity_ttm")
    gross_margin = _fundamental_value(bundle, "gross_margin_ttm")
    earnings_yield = _fundamental_value(bundle, "earnings_yield_ttm")

    reasons: list[str] = []
    failed = False

    if pe is not None and pe > 0:
        if pe > 100:
            reasons.append(f"PE too high ({pe:.0f})")
            failed = True
        elif pe > 40:
            reasons.append(f"Elevated PE ({pe:.0f})")
        else:
            reasons.append(f"Reasonable PE ({pe:.0f})")
    else:
        reasons.append("PE unknown")

    if debt_eq is not None and debt_eq > 5.0:
        reasons.append(f"High debt/equity ({debt_eq:.1f})")
        failed = True

    if gross_margin is not None and gross_margin < -0.5:
        reasons.append("Negative gross margin")
        failed = True

    if earnings_yield is not None and earnings_yield < -0.20:
        reasons.append("Deeply negative earnings yield")
        failed = True

    score = 20.0 if failed else 70.0
    return ScorecardComponent(
        name="fundamentals",
        category="fundamental",
        score=score,
        state=ComponentState.fail if failed else ComponentState.pass_,
        weight=_COMPONENT_WEIGHTS["fundamentals"],
        passed=not failed,
        reason="; ".join(reasons) if reasons else "No fundamental data",
    )


def _score_event_risk(bundle: FactsBundle, as_of: date) -> ScorecardComponent:
    blackout_days = 14
    window_end = as_of + timedelta(days=blackout_days)

    for event in bundle.sections.earnings_events:
        event_date = _parse_date(event.effective_date)
        if event_date is None:
            continue
        if as_of <= event_date <= window_end:
            days_until = (event_date - as_of).days
            return ScorecardComponent(
                name="event_risk",
                category="event",
                score=10.0,
                state=ComponentState.warn,
                weight=_COMPONENT_WEIGHTS["event_risk"],
                passed=True,
                reason=f"Earnings in {days_until}d (blackout period)",
            )
        if event_date < as_of and (as_of - event_date).days <= 2:
            return ScorecardComponent(
                name="event_risk",
                category="event",
                score=40.0,
                state=ComponentState.warn,
                weight=_COMPONENT_WEIGHTS["event_risk"],
                passed=True,
                reason="Recent earnings — watch for post-earnings drift",
            )
    return ScorecardComponent(
        name="event_risk",
        category="event",
        score=90.0,
        weight=_COMPONENT_WEIGHTS["event_risk"],
        reason="No event risk in blackout window",
    )


def _score_insider_activity(bundle: FactsBundle) -> ScorecardComponent:
    txs = bundle.sections.insider_transactions
    if not txs:
        return ScorecardComponent(
            name="insider_activity",
            category="insider",
            score=50.0,
            weight=_COMPONENT_WEIGHTS["insider_activity"],
            reason="No insider transactions recorded",
        )
    buys = sum(1 for t in txs if t.transaction_type.lower().startswith(("buy", "p")))
    sells = sum(1 for t in txs if t.transaction_type.lower().startswith(("sell", "s")))
    total = buys + sells
    if total == 0:
        return ScorecardComponent(
            name="insider_activity",
            category="insider",
            score=50.0,
            weight=_COMPONENT_WEIGHTS["insider_activity"],
            reason="Non-trading insider activity",
        )
    net_ratio = (buys - sells) / total
    if net_ratio <= 0:
        return ScorecardComponent(
            name="insider_activity",
            category="insider",
            score=20.0,
            state=ComponentState.warn,
            weight=_COMPONENT_WEIGHTS["insider_activity"],
            reason=f"Net insider selling ({sells}/{total} transactions)",
        )
    score = min(85.0, 50.0 + net_ratio * 50 * (total / 5))
    return ScorecardComponent(
        name="insider_activity",
        category="insider",
        score=score,
        weight=_COMPONENT_WEIGHTS["insider_activity"],
        reason=f"Net insider buying ({buys}/{total} transactions)",
    )


def _score_attention_crowding(bundle: FactsBundle) -> ScorecardComponent:
    mentions = bundle.sections.attention_mentions
    if len(mentions) < 2:
        return ScorecardComponent(
            name="attention_crowding",
            category="sentiment",
            score=80.0,
            weight=_COMPONENT_WEIGHTS["attention_crowding"],
            reason="Low attention levels",
        )
    values = [m.count for m in mentions]
    latest = values[-1]
    avg = mean(values)
    std = stdev(values) if len(values) > 1 else 0.0

    if std <= 0:
        return ScorecardComponent(
            name="attention_crowding",
            category="sentiment",
            score=70.0,
            weight=_COMPONENT_WEIGHTS["attention_crowding"],
            reason="Stable mention levels",
        )
    z_score = (latest - avg) / std
    if z_score > 3.0:
        return ScorecardComponent(
            name="attention_crowding",
            category="sentiment",
            score=10.0,
            state=ComponentState.warn,
            weight=_COMPONENT_WEIGHTS["attention_crowding"],
            reason=f"Extreme attention spike (z={z_score:.1f})",
        )
    if z_score > 2.0:
        return ScorecardComponent(
            name="attention_crowding",
            category="sentiment",
            score=35.0,
            state=ComponentState.warn,
            weight=_COMPONENT_WEIGHTS["attention_crowding"],
            reason=f"Elevated attention (z={z_score:.1f})",
        )
    return ScorecardComponent(
        name="attention_crowding",
        category="sentiment",
        score=70.0,
        weight=_COMPONENT_WEIGHTS["attention_crowding"],
        reason="Normal attention levels",
    )


def _score_portfolio_fit(
    symbol: str,
    portfolio: PortfolioContext,
) -> ScorecardComponent:
    existing = portfolio.positions.get(symbol)
    if existing is None or portfolio.equity <= 0:
        pos_count = len(portfolio.positions)
        if pos_count >= portfolio.max_positions:
            return ScorecardComponent(
                name="portfolio_fit",
                category="portfolio",
                score=20.0,
                state=ComponentState.warn,
                weight=_COMPONENT_WEIGHTS["portfolio_fit"],
                passed=True,
                reason=f"Portfolio full ({pos_count}/{portfolio.max_positions})",
            )
        return ScorecardComponent(
            name="portfolio_fit",
            category="portfolio",
            score=80.0,
            weight=_COMPONENT_WEIGHTS["portfolio_fit"],
            reason="Room in portfolio",
        )
    mv = existing.market_value or 0
    pct = (mv / portfolio.equity) * 100
    if pct > portfolio.max_position_pct * 100:
        return ScorecardComponent(
            name="portfolio_fit",
            category="portfolio",
            score=15.0,
            state=ComponentState.warn,
            weight=_COMPONENT_WEIGHTS["portfolio_fit"],
            passed=True,
            reason=f"Overweight ({pct:.1f}% of equity)",
        )
    if pct > (portfolio.max_position_pct * 100 * 0.5):
        return ScorecardComponent(
            name="portfolio_fit",
            category="portfolio",
            score=50.0,
            weight=_COMPONENT_WEIGHTS["portfolio_fit"],
            reason=f"Significant position ({pct:.1f}% of equity)",
        )
    return ScorecardComponent(
        name="portfolio_fit",
        category="portfolio",
        score=80.0,
        weight=_COMPONENT_WEIGHTS["portfolio_fit"],
        reason=f"Healthy position size ({pct:.1f}% of equity)",
    )


def _score_position_risk(
    symbol: str,
    portfolio: PortfolioContext,
) -> ScorecardComponent:
    existing = portfolio.positions.get(symbol)
    if existing is None or existing.avg_cost <= 0:
        return ScorecardComponent(
            name="position_risk",
            category="risk",
            score=50.0,
            weight=_COMPONENT_WEIGHTS["position_risk"],
            reason="No position",
        )
    price = existing.current_price or existing.avg_cost
    pl_pct = ((price - existing.avg_cost) / existing.avg_cost) * 100
    if pl_pct <= -15:
        return ScorecardComponent(
            name="position_risk",
            category="risk",
            score=10.0,
            state=ComponentState.warn,
            weight=_COMPONENT_WEIGHTS["position_risk"],
            reason=f"Position down {pl_pct:.1f}%",
        )
    if pl_pct <= -5:
        return ScorecardComponent(
            name="position_risk",
            category="risk",
            score=35.0,
            weight=_COMPONENT_WEIGHTS["position_risk"],
            reason=f"Position down {pl_pct:.1f}%",
        )
    if pl_pct >= 15:
        return ScorecardComponent(
            name="position_risk",
            category="risk",
            score=80.0,
            weight=_COMPONENT_WEIGHTS["position_risk"],
            reason=f"Position up {pl_pct:.1f}%",
        )
    return ScorecardComponent(
        name="position_risk",
        category="risk",
        score=60.0,
        weight=_COMPONENT_WEIGHTS["position_risk"],
        reason=f"Position near cost basis ({pl_pct:.1f}%)",
    )


def _score_cash_impact(
    symbol: str,
    portfolio: PortfolioContext,
) -> ScorecardComponent:
    existing = portfolio.positions.get(symbol)
    if existing is not None:
        return ScorecardComponent(
            name="cash_impact",
            category="portfolio",
            score=80.0,
            weight=_COMPONENT_WEIGHTS["cash_impact"],
            reason="Already invested",
        )
    if portfolio.cash <= 0:
        return ScorecardComponent(
            name="cash_impact",
            category="portfolio",
            score=10.0,
            state=ComponentState.warn,
            weight=_COMPONENT_WEIGHTS["cash_impact"],
            passed=True,
            reason="No available cash",
        )
    est_size = min(portfolio.cash, portfolio.equity * 0.1)
    cash_pct = (est_size / portfolio.cash) * 100 if portfolio.cash > 0 else 0
    if cash_pct >= 50:
        return ScorecardComponent(
            name="cash_impact",
            category="portfolio",
            score=70.0,
            weight=_COMPONENT_WEIGHTS["cash_impact"],
            reason="Adequate cash available",
        )
    if cash_pct >= 20:
        return ScorecardComponent(
            name="cash_impact",
            category="portfolio",
            score=50.0,
            weight=_COMPONENT_WEIGHTS["cash_impact"],
            reason="Limited cash",
        )
    return ScorecardComponent(
        name="cash_impact",
        category="portfolio",
        score=30.0,
        weight=_COMPONENT_WEIGHTS["cash_impact"],
        reason="Tight cash position",
    )


def _score_data_quality(bundle: FactsBundle) -> ScorecardComponent:
    missing = 0
    expected = ["last", "rsi_14", "macd_cross", "rvol", "atr_pct_14", "bollinger_width"]
    for readout_id in expected:
        if _readout_value(bundle, readout_id) is None:
            missing += 1
    total = len(expected)
    quality_pct = ((total - missing) / total) * 100
    if quality_pct >= 80:
        return ScorecardComponent(
            name="data_quality",
            category="data",
            score=90.0,
            weight=_COMPONENT_WEIGHTS["data_quality"],
            reason="Good data coverage",
        )
    if quality_pct >= 50:
        return ScorecardComponent(
            name="data_quality",
            category="data",
            score=50.0,
            state=ComponentState.warn,
            weight=_COMPONENT_WEIGHTS["data_quality"],
            passed=True,
            reason=f"Partial data ({total - missing}/{total} indicators)",
        )
    return ScorecardComponent(
        name="data_quality",
        category="data",
        score=10.0,
        state=ComponentState.fail,
        weight=_COMPONENT_WEIGHTS["data_quality"],
        passed=False,
        reason=f"Insufficient data ({total - missing}/{total} indicators)",
    )


# -- gates --


def _apply_gates(
    components: dict[str, ScorecardComponent],
    portfolio: PortfolioContext,
    as_of: date,
    symbol: str = "",
) -> list[str]:
    warnings: list[str] = []

    if portfolio.regime == "RISK_OFF":
        warnings.append("Market regime: RISK_OFF — reducing all scores")

    dq = components.get("data_quality")
    if dq and dq.state == ComponentState.fail:
        warnings.append("Data quality insufficient")

    if portfolio.regime == "CAUTION":
        warnings.append("Market regime: CAUTION — adopting defensive posture")

    for w in warnings:
        logger.warning("gate_triggered", symbol=symbol, warning=w)

    return warnings


def _compute_total_score(
    components: list[ScorecardComponent],
    regime: str,
) -> float:
    total_weight = 0.0
    weighted_sum = 0.0
    regime_multiplier = {"RISK_ON": 1.0, "CAUTION": 0.6, "RISK_OFF": 0.2}.get(regime, 1.0)

    for c in components:
        if c.weight <= 0:
            continue
        total_weight += c.weight
        effective_score = c.score * regime_multiplier
        weighted_sum += effective_score * c.weight

    if total_weight <= 0:
        return 0.0
    return round(weighted_sum / total_weight, 2)


def _recommendation_from_score(
    total_score: float,
    has_position: bool,
    components: dict[str, ScorecardComponent],
) -> Recommendation:
    dq = components.get("data_quality")
    if dq and dq.state == ComponentState.fail:
        return Recommendation.do_nothing

    for threshold, pos_rec, new_rec in _RECOMMENDATION_THRESHOLDS:
        if total_score >= threshold:
            return pos_rec if has_position else new_rec
    if has_position:
        return Recommendation.reduce if total_score < 25 else Recommendation.do_nothing
    return Recommendation.do_nothing


# -- main engine --


def generate_scorecards(
    bundles: dict[str, FactsBundle],
    portfolio: PortfolioContext,
    as_of: datetime | None = None,
    spy_bundle: FactsBundle | None = None,
) -> list[Scorecard]:
    now = as_of or datetime.now(UTC)
    today = now.date()
    scorecards: list[Scorecard] = []

    all_symbols = set(bundles.keys())
    if spy_bundle and spy_bundle.metadata.symbol in all_symbols:
        all_symbols.discard(spy_bundle.metadata.symbol)

    for symbol in all_symbols:
        bundle = bundles.get(symbol)
        if not bundle:
            continue

        has_position = symbol in portfolio.positions

        components: dict[str, ScorecardComponent] = {}
        components["technical_trend"] = _score_technical_trend(bundle)
        components["momentum"] = _score_momentum(bundle)
        components["volatility"] = _score_volatility(bundle)
        components["participation"] = _score_participation(bundle)
        components["relative_strength"] = _score_relative_strength(bundle, spy_bundle)
        components["fundamentals"] = _score_fundamentals(bundle)
        components["event_risk"] = _score_event_risk(bundle, today)
        components["insider_activity"] = _score_insider_activity(bundle)
        components["attention_crowding"] = _score_attention_crowding(bundle)
        components["portfolio_fit"] = _score_portfolio_fit(symbol, portfolio)
        components["position_risk"] = _score_position_risk(symbol, portfolio)
        components["cash_impact"] = _score_cash_impact(symbol, portfolio)
        components["data_quality"] = _score_data_quality(bundle)

        _apply_gates(components, portfolio, today, symbol=symbol)
        total_score = _compute_total_score(list(components.values()), portfolio.regime)

        dq = components.get("data_quality")
        data_quality = dq.state if dq else ComponentState.pass_

        recommendation = _recommendation_from_score(total_score, has_position, components)

        scorecard = Scorecard(
            symbol=symbol,
            as_of=now,
            recommendation=recommendation,
            confidence=round(total_score / 100, 2),
            total_score=total_score,
            data_quality=data_quality,
            components=list(components.values()),
            facts_hash=_compute_hash(bundle),
        )
        scorecards.append(scorecard)

    scorecards.sort(key=lambda s: s.total_score, reverse=True)
    return scorecards


def _compute_hash(bundle: FactsBundle) -> str:
    import hashlib

    parts: list[str] = []
    parts.append(bundle.metadata.symbol)
    parts.append(str(bundle.metadata.as_of))
    for r in bundle.sections.readouts:
        parts.append(r.definition.readout_id)
        for o in r.observations:
            parts.append(f"{o.effective_date}={o.value}")
    for f in bundle.sections.fundamentals:
        parts.append(f"{f.metric_id}={f.value}")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
