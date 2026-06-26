from __future__ import annotations

from datetime import date, datetime
from typing import Any

from alpha_quant.contracts.alpha_lake import (
    INDICATOR_FIELD_MAP,
    BarObservation,
    EarningsEvent,
    FundamentalMetric,
    InsiderTransaction,
    MentionObservation,
    PriceObservation,
    SymbolObservations,
    TechnicalObservations,
)


def parse_date(raw: Any) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    return date.today()


def opt_float(raw: Any) -> float | None:
    if raw is None:
        return None
    return float(raw)


def parse_bar_obs(row: dict[str, Any]) -> BarObservation:
    return BarObservation(
        effective_date=parse_date(row.get("effective_date") or row.get("date")),
        open=float(row.get("open", 0.0)),
        high=float(row.get("high", 0.0)),
        low=float(row.get("low", 0.0)),
        close=float(row.get("close", 0.0)),
        volume=float(row.get("volume", 0.0)),
        adj_close=opt_float(row.get("adj_close") or row.get("adjusted_close")),
    )


def parse_price_observation(
    bars: list[BarObservation],
    tech: TechnicalObservations | None,
) -> PriceObservation | None:
    if not bars:
        return None
    last = bars[-1]
    prev_close = bars[-2].close if len(bars) >= 2 else None
    return PriceObservation(
        latest_close=last.close,
        latest_volume=last.volume,
        previous_close=prev_close,
        daily_high=last.high,
        daily_low=last.low,
        daily_open=last.open,
    )


def parse_technical_observations(raw: dict[str, list[Any]]) -> TechnicalObservations | None:
    technical = TechnicalObservations()
    has_data = False
    additional: dict[str, float | None] = {}

    for key, values in raw.items():
        if key in (
            "effective_date",
            "security_id",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "source_id",
        ):
            continue
        latest_val = None
        if values and len(values) > 0:
            raw_v = values[-1]
            latest_val = float(raw_v) if raw_v is not None else None

        field = INDICATOR_FIELD_MAP.get(key)
        if field and latest_val is not None:
            setattr(technical, field, latest_val)
            has_data = True
        elif latest_val is not None:
            additional[key] = latest_val
            has_data = True

    if not has_data:
        return None

    if additional:
        object.__setattr__(technical, "additional", additional)
    return technical


def parse_fundamental_obs(row: dict[str, Any]) -> FundamentalMetric:
    return FundamentalMetric(
        metric_id=row.get("metric_id", ""),
        name=row.get("name", ""),
        category=row.get("category", ""),
        period_end=row.get("period_end"),
        value=opt_float(row.get("value")),
        unit=row.get("unit", ""),
        state=row.get("state", ""),
        tone=row.get("tone", ""),
        quality_status=row.get("quality_status", ""),
        available_at=row.get("available_at"),
    )


def parse_insider_obs(row: dict[str, Any]) -> InsiderTransaction:
    return InsiderTransaction(
        effective_date=str(row.get("effective_date", "")),
        transaction_type=str(row.get("transaction_code", row.get("transaction_type", ""))),
        shares=opt_float(row.get("shares")),
        price=opt_float(row.get("price")),
        value=opt_float(row.get("value")),
    )


def parse_earnings_obs(row: dict[str, Any]) -> EarningsEvent:
    return EarningsEvent(
        effective_date=str(row.get("effective_date", "")),
        symbol=str(row.get("symbol", row.get("security_id", ""))),
    )


def parse_mention_obs(row: dict[str, Any]) -> MentionObservation:
    return MentionObservation(
        effective_date=str(row.get("effective_date", "")),
        count=int(row.get("mention_count", row.get("count", 0))),
        source=str(row.get("source_id", "alpha_lake")),
    )


def parse_symbol_observations(symbol: str, raw: dict[str, Any]) -> SymbolObservations:
    bars = [parse_bar_obs(b) for b in raw.get("bars", [])]
    tech = parse_technical_observations(raw.get("indicators", {}))
    price = parse_price_observation(bars, tech)

    fundamentals = [parse_fundamental_obs(m) for m in raw.get("fundamentals", [])]
    insider = [parse_insider_obs(t) for t in raw.get("insider_transactions", [])]
    earnings = [parse_earnings_obs(e) for e in raw.get("earnings_events", [])]
    mentions = [parse_mention_obs(m) for m in raw.get("attention_mentions", [])]

    return SymbolObservations(
        symbol=symbol,
        price=price,
        technical=tech,
        fundamentals=fundamentals,
        insider_transactions=insider,
        earnings_events=earnings,
        attention_mentions=mentions,
        bars=bars,
    )
