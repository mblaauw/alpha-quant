from __future__ import annotations

from datetime import date, datetime
from typing import Any

from alpha_quant.contracts.alpha_lake import (
    EarningsEvent,
    FactsBundle,
    FactsBundleMetadata,
    FactsBundleSections,
    FundamentalMetric,
    InsiderTransaction,
    MentionObservation,
    ReadoutDefinition,
    ReadoutItem,
    ReadoutObservation,
    SymbolMutationResult,
    SymbolRegistryItem,
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
    readouts_raw = raw.get("readouts", [])
    if isinstance(readouts_raw, dict):
        return readouts_raw.get("readouts", readouts_raw.get("items", []))
    return readouts_raw if isinstance(readouts_raw, list) else []


def _resolve_price_as_readouts(raw: dict[str, Any]) -> list[ReadoutItem]:
    price = raw.get("price", {})
    if not isinstance(price, dict):
        return []
    items: list[ReadoutItem] = []
    numeric_keys = {
        "last",
        "high",
        "low",
        "open",
        "volume",
        "change",
        "change_pct",
        "dollar_volume",
    }
    for k in numeric_keys:
        v = price.get(k)
        if v is not None:
            try:
                val = float(v)
                items.append(
                    ReadoutItem(
                        definition=ReadoutDefinition(
                            readout_id=f"price.{k}",
                            label=f"Price {k}",
                            category="price",
                        ),
                        observations=[
                            ReadoutObservation(
                                effective_date=str(price.get("latest_date", "")),
                                value=val,
                            )
                        ],
                    )
                )
            except (ValueError, TypeError):  # fmt: skip
                pass
    return items


def parse_facts_bundle_sections(raw: dict[str, Any]) -> FactsBundleSections:
    raw_readouts = _resolve_readouts(raw)
    items: list[ReadoutItem] = [parse_readout_item(r) for r in raw_readouts]
    if isinstance(raw, dict):
        items.extend(_resolve_price_as_readouts(raw))
    return FactsBundleSections(
        readouts=items,
        fundamentals=[
            parse_fundamental_obs(m)
            for m in (
                raw.get("fundamentals", {}).get("metrics", [])
                if isinstance(raw.get("fundamentals"), dict)
                else raw.get("fundamentals", [])
            )
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
