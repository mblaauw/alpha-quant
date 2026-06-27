from __future__ import annotations

from datetime import date, datetime
from typing import Any

from alpha_quant.contracts.alpha_lake import (
    INDICATOR_FIELD_MAP,
    BarObservation,
    EarningsEvent,
    FactsBundle,
    FactsBundleMetadata,
    FactsBundleSections,
    FundamentalMetric,
    InsiderTransaction,
    MentionObservation,
    PriceObservation,
    ReadoutDefinition,
    ReadoutItem,
    ReadoutObservation,
    SymbolMutationResult,
    SymbolObservations,
    SymbolRegistryItem,
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

    skip_keys = {
        "effective_date",
        "security_id",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source_id",
        "available_at",
        "ingested_at",
        "source_published_at",
        "validated_at",
        "source_fetch_id",
        "raw_payload_hash",
        "ingestion_run_id",
        "content_hash",
        "version_hash",
        "quality_status",
        "normalization_version",
        "schema_version",
        "parser_version",
    }
    for key, values in raw.items():
        if key in skip_keys:
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


# -- Facts-bundle parsing --


def parse_readout_definition(raw: dict[str, Any]) -> ReadoutDefinition:
    return ReadoutDefinition(
        readout_id=str(raw.get("definition_id", raw.get("readout_id", ""))),
        label=str(raw.get("name", raw.get("label", ""))),
        category=str(raw.get("category", "")),
        unit=str(raw.get("unit", "")),
    )


def parse_readout_observation(raw: dict[str, Any]) -> ReadoutObservation:
    return ReadoutObservation(
        effective_date=str(raw.get("as_of", raw.get("effective_date", ""))),
        value=opt_float(raw.get("value")),
        normalized=opt_float(raw.get("normalized")),
    )


def parse_readout_item(raw: dict[str, Any]) -> ReadoutItem:
    obs_raw = raw.get("observation", raw.get("observations", []))
    if isinstance(obs_raw, dict):
        observations = [parse_readout_observation(obs_raw)]
    else:
        observations = [parse_readout_observation(o) for o in obs_raw]
    return ReadoutItem(
        definition=parse_readout_definition(raw.get("definition", {})),
        observations=observations,
    )


def parse_facts_bundle_metadata(raw: dict[str, Any]) -> FactsBundleMetadata:
    return FactsBundleMetadata(
        symbol=str(raw.get("symbol", "")),
        as_of=datetime.fromisoformat(str(raw.get("as_of", "")).replace("Z", "+00:00")),
        snapshot_id=raw.get("snapshot_id"),
        categories=list(raw.get("categories", [])),
    )


def _resolve_readouts(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle both list and dict formats for readouts section."""
    readouts_raw = raw.get("readouts", [])
    if isinstance(readouts_raw, dict):
        return readouts_raw.get("readouts", readouts_raw.get("items", []))
    return readouts_raw if isinstance(readouts_raw, list) else []


def parse_facts_bundle_sections(raw: dict[str, Any]) -> FactsBundleSections:
    return FactsBundleSections(
        readouts=[parse_readout_item(r) for r in _resolve_readouts(raw)],
        fundamentals=[
            parse_fundamental_obs(m) for m in raw.get("fundamentals", {}).get("metrics", [])
        ],
        insider_transactions=[
            parse_insider_obs(t) for t in raw.get("insider_tx", raw.get("insider_transactions", []))
        ],
        earnings_events=[parse_earnings_obs(e) for e in raw.get("earnings_events", [])],
        attention_mentions=[
            parse_mention_obs(m)
            for m in raw.get("attention_metrics", raw.get("attention_mentions", []))
        ],
    )


def parse_facts_bundle(raw: dict[str, Any]) -> FactsBundle:
    return FactsBundle(
        metadata=parse_facts_bundle_metadata(raw),
        sections=parse_facts_bundle_sections(raw.get("sections", raw)),
    )


def parse_symbol_registry_item(raw: dict[str, Any]) -> SymbolRegistryItem:
    return SymbolRegistryItem(
        symbol=str(raw.get("symbol", "")),
        added_at=str(raw.get("added_at", "")),
        active=bool(raw.get("active", True)),
    )


def parse_symbol_mutation_result(raw: dict[str, Any]) -> SymbolMutationResult:
    return SymbolMutationResult(
        symbol=str(raw.get("symbol", "")),
        status=str(raw.get("status", "")),
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
