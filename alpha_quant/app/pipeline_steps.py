"""Pipeline step functions with typed inputs and outputs.

Each step is a function that takes explicit inputs and returns a typed
result model. Steps do not call ``store.save_*()`` — the orchestrator
handles persistence.

Currently called from ``pipeline.run()`` step-by-step. Each function
encapsulates exactly the logic of one ``with _time_step(...)`` block.
"""

from __future__ import annotations

from datetime import date

import structlog

from alpha_quant.app.step_models import (
    DeriveResult,
    LoadBarsResult,
    ValidateResult,
)
from alpha_quant.domain.derive import backfill_indicator_state
from alpha_quant.domain.events import (
    DataIngested,
    DataQuarantined,
    DomainEvent,
    ErrorOccurred,
    IndicatorStateUpdated,
    SourceDegraded,
    StalenessHaltSet,
)
from alpha_quant.domain.models import (
    Bar,
    IndicatorState,
)
from alpha_quant.domain.validate import validate_bars
from alpha_quant.ports.market_data import MarketData
from alpha_quant.ports.store import Store

logger = structlog.get_logger()


def load_bars_step(
    run_date: date,
    symbols: list[str],
    store: Store,
    market_data: MarketData | None,
    lookback_days: int,
    run_id: str,
) -> LoadBarsResult:
    """Load bars from store or market_data for all symbols."""
    lookback_start = date.fromordinal(run_date.toordinal() - lookback_days)
    all_bars: dict[str, list[Bar]] = {}
    prices: dict[str, float] = {}
    events: list[DomainEvent] = []

    for symbol in symbols:
        bars: list[Bar] = []
        try:
            bars = store.load_bars(symbol, lookback_start, run_date)
        except Exception:
            logger.warning("store_bar_load_failed", symbol=symbol)
        if not bars and market_data is not None:
            try:
                bars = market_data.daily_bars(symbol, lookback_start, run_date)
                if bars:
                    events.append(
                        DataIngested(
                            run_id=run_id,
                            source="pipeline",
                            connector="market_data",
                            symbol=symbol,
                            records=len(bars),
                        )
                    )
            except Exception:
                logger.exception("market_data_bar_load_failed", symbol=symbol)
        if bars:
            all_bars[symbol] = bars
            prices[symbol] = bars[-1].close
        else:
            events.append(
                SourceDegraded(
                    run_id=run_id,
                    source="pipeline",
                    source_name=symbol,
                    fallback="skip",
                )
            )
            events.append(
                ErrorOccurred(
                    run_id=run_id,
                    source="pipeline",
                    error="No bar data from store or market_data",
                    context={"symbol": symbol, "operation": "bar_load"},
                )
            )

    return LoadBarsResult(all_bars=all_bars, prices=prices, events=events)


def validate_step(
    all_bars: dict[str, list[Bar]],
    run_id: str,
) -> ValidateResult:
    """Validate bars and emit quarantine/halt events."""
    events: list[DomainEvent] = []
    halted = False

    for symbol, bars in all_bars.items():
        if not bars:
            continue
        results = validate_bars(bars)
        for vr in results:
            events.append(
                DataQuarantined(
                    run_id=run_id,
                    source="pipeline",
                    symbol=symbol,
                    reason=vr.check,
                    detail="; ".join(vr.issues),
                )
            )
            if vr.severity == "HALT":
                halted = True
                events.append(
                    StalenessHaltSet(
                        run_id=run_id,
                        source="pipeline",
                        symbol=symbol,
                        hours_since_last=0.0,
                    )
                )

    return ValidateResult(events=events, halted=halted)


def derive_step(
    all_bars: dict[str, list[Bar]],
    run_id: str,
) -> DeriveResult:
    """Backfill indicators for all symbols."""
    indicator_states: dict[str, IndicatorState] = {}
    events: list[DomainEvent] = []

    for symbol, bars in all_bars.items():
        if bars:
            try:
                indicator_states[symbol] = backfill_indicator_state(bars)
                events.append(
                    IndicatorStateUpdated(
                        run_id=run_id,
                        source="pipeline",
                        symbol=symbol,
                        indicator_count=len(bars),
                    )
                )
            except Exception as e:
                logger.exception("indicator_backfill_failed", symbol=symbol)
                events.append(
                    ErrorOccurred(
                        run_id=run_id,
                        source="pipeline",
                        error=str(e),
                        context={"symbol": symbol, "operation": "indicator_backfill"},
                    )
                )

    return DeriveResult(indicator_states=indicator_states, events=events)
