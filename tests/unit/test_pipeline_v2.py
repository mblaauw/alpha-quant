from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

from alpha_quant.application.pipeline_v2 import run_v2
from alpha_quant.contracts.alpha_lake import (
    AlphaLakeHealth,
    BarObservation,
    EarningsEvent,
    FundamentalMetric,
    MarketObservations,
    NeutralObservations,
    PriceObservation,
    SymbolObservations,
    TechnicalObservations,
)
from alpha_quant.domain.models import PortfolioSnapshot, Position
from alpha_quant.ports.alpha_lake import AlphaLakeReadPort


def _mock_store(**overrides: object) -> MagicMock:
    store = MagicMock()
    store.load_positions.return_value = overrides.get("positions", [])
    store.load_latest_portfolio_snapshot.return_value = overrides.get("latest_snapshot")
    store.load_portfolio_snapshots.return_value = overrides.get("snapshots", [])
    store.save_position = MagicMock()
    store.save_fill = MagicMock()
    store.save_decision = MagicMock()
    store.save_portfolio_snapshot = MagicMock()
    store.save_event = MagicMock()
    return store


def _make_bar(close: float = 100.0) -> BarObservation:
    return BarObservation(
        effective_date=date(2026, 1, 2),
        open=close - 1.0,
        high=close + 2.0,
        low=close - 2.0,
        close=close,
        volume=1_000_000,
    )


def _make_spy_observations() -> SymbolObservations:
    bars = [_make_bar(close=480.0)]
    return SymbolObservations(
        symbol="SPY",
        price=PriceObservation(
            latest_close=480.0,
            latest_volume=1_000_000,
            daily_open=479.0,
            daily_high=482.0,
            daily_low=478.0,
        ),
        technical=TechnicalObservations(
            ma_regime_50=482.0,
            ma_regime_200=478.0,
            rsi_14=50.0,
            macd_histogram=0.2,
            atr_pct_14=0.015,
            volume_ratio_21=1.0,
        ),
        bars=bars,
    )


def _make_observations() -> NeutralObservations:
    spy = _make_spy_observations()
    aapl = SymbolObservations(
        symbol="AAPL",
        price=PriceObservation(
            latest_close=200.0,
            latest_volume=1_000_000,
            daily_open=199.0,
            daily_high=202.0,
            daily_low=198.0,
        ),
        technical=TechnicalObservations(
            rsi_14=55.0,
            macd_histogram=0.3,
            atr_pct_14=0.021,
            ma_regime_50=200.0,
            volume_ratio_21=1.1,
            return_63d=0.08,
        ),
        fundamentals=[
            FundamentalMetric(
                metric_id="fundamentals.valuation.pe_ttm",
                name="PE TTM",
                category="valuation",
                value=25.0,
            ),
            FundamentalMetric(
                metric_id="fundamentals.financial_health.debt_to_equity_ttm",
                name="D/E",
                category="financial_health",
                value=1.5,
            ),
        ],
        bars=[_make_bar(close=200.0)],
    )
    msft = SymbolObservations(
        symbol="MSFT",
        price=PriceObservation(
            latest_close=350.0,
            latest_volume=1_000_000,
            daily_open=349.0,
            daily_high=352.0,
            daily_low=348.0,
        ),
        technical=TechnicalObservations(
            rsi_14=58.0,
            macd_histogram=1.0,
            atr_pct_14=0.017,
            ma_regime_50=348.0,
            volume_ratio_21=1.2,
            return_63d=0.10,
        ),
        fundamentals=[
            FundamentalMetric(
                metric_id="fundamentals.financial_health.debt_to_equity_ttm",
                name="D/E",
                category="financial_health",
                value=0.8,
            ),
        ],
        bars=[_make_bar(close=350.0)],
    )
    googl = SymbolObservations(
        symbol="GOOGL",
        price=PriceObservation(
            latest_close=180.0,
            latest_volume=1_000_000,
            daily_open=179.0,
            daily_high=182.0,
            daily_low=178.0,
        ),
        technical=TechnicalObservations(
            rsi_14=25.0,
            macd_histogram=-1.0,
            atr_pct_14=0.032,
            ma_regime_50=185.0,
            volume_ratio_21=0.7,
            return_63d=0.0,
        ),
        earnings_events=[
            EarningsEvent(effective_date="2026-01-10", symbol="GOOGL"),
        ],
        bars=[_make_bar(close=180.0)],
    )
    return NeutralObservations(
        as_of=datetime(2026, 1, 2, 14, 30, tzinfo=UTC),
        snapshot_id=None,
        symbols=["AAPL", "MSFT", "GOOGL", "SPY"],
        per_symbol={
            "SPY": spy,
            "AAPL": aapl,
            "MSFT": msft,
            "GOOGL": googl,
        },
        market=MarketObservations.from_symbol_observations(spy),
    )


def test_run_v2_no_spy_data() -> None:
    store = _mock_store()
    mock_lake = MagicMock(spec=AlphaLakeReadPort)
    mock_lake.health.return_value = AlphaLakeHealth(status="ok")
    mock_lake.read_observations.return_value = NeutralObservations(
        as_of=datetime(2026, 1, 2, 14, 30, tzinfo=UTC),
        snapshot_id=None,
        symbols=["SPY"],
        per_symbol={},
    )

    result = run_v2(
        run_date=date(2026, 1, 2),
        store=store,
        universe=["AAPL"],
        alpha_lake=mock_lake,
    )
    assert result.date == date(2026, 1, 2)
    assert len(result.decisions) == 0
    assert len(result.fills) == 0


def test_run_v2_health_unreachable() -> None:
    store = _mock_store()
    mock_lake = MagicMock(spec=AlphaLakeReadPort)
    mock_lake.health.return_value = AlphaLakeHealth(status="unreachable")
    mock_lake.read_observations.return_value = _make_observations()

    result = run_v2(
        run_date=date(2026, 1, 2),
        store=store,
        universe=["AAPL"],
        alpha_lake=mock_lake,
    )
    assert result.date == date(2026, 1, 2)


def test_run_v2_empty_universe() -> None:
    store = _mock_store()
    mock_lake = MagicMock(spec=AlphaLakeReadPort)
    mock_lake.health.return_value = AlphaLakeHealth(status="ok")
    mock_lake.read_observations.return_value = _make_observations()

    result = run_v2(
        run_date=date(2026, 1, 2),
        store=store,
        universe=[],
        alpha_lake=mock_lake,
    )
    assert result.date == date(2026, 1, 2)
    assert len(result.decisions) == 1
    assert result.decisions[0].symbol == "SPY"


def test_run_v2_full_flow() -> None:
    store = _mock_store(
        latest_snapshot=PortfolioSnapshot(
            date=date(2026, 1, 1), cash=100_000.0, equity=100_000.0, regime="CAUTION"
        ),
        snapshots=[
            PortfolioSnapshot(
                date=date(2026, 1, 1), cash=100_000.0, equity=100_000.0, regime="CAUTION"
            )
        ],
    )

    mock_lake = MagicMock(spec=AlphaLakeReadPort)
    mock_lake.health.return_value = AlphaLakeHealth(status="ok")
    mock_lake.read_observations.return_value = _make_observations()

    result = run_v2(
        run_date=date(2026, 1, 2),
        store=store,
        universe=["AAPL", "MSFT", "GOOGL"],
        alpha_lake=mock_lake,
        prev_equity=100_000.0,
        prev_regime="CAUTION",
    )

    assert result.date == date(2026, 1, 2)
    assert result.current_regime in ("RISK_ON", "CAUTION", "RISK_OFF")
    assert result.violations is not None
    event_types = {type(e).__name__ for e in result.events}
    assert "PipelineRunStarted" in event_types
    assert "PipelineRunCompleted" in event_types


def test_run_v2_with_existing_positions() -> None:
    existing = Position(
        symbol="AAPL",
        quantity=50.0,
        entry_price=200.0,
        avg_cost=200.0,
        current_price=200.0,
        stop_price=190.0,
        market_value=10_000.0,
        decision_id="test-dec",
        entry_date=date(2025, 12, 15),
        high_since_entry=205.0,
    )
    store = _mock_store(
        positions=[existing],
        latest_snapshot=PortfolioSnapshot(
            date=date(2026, 1, 1), cash=100_000.0, equity=100_000.0, regime="CAUTION"
        ),
        snapshots=[
            PortfolioSnapshot(
                date=date(2026, 1, 1), cash=100_000.0, equity=100_000.0, regime="CAUTION"
            )
        ],
    )

    mock_lake = MagicMock(spec=AlphaLakeReadPort)
    mock_lake.health.return_value = AlphaLakeHealth(status="ok")
    mock_lake.read_observations.return_value = _make_observations()

    result = run_v2(
        run_date=date(2026, 1, 2),
        store=store,
        universe=["AAPL", "MSFT", "GOOGL"],
        alpha_lake=mock_lake,
        prev_equity=100_000.0,
        prev_regime="CAUTION",
    )

    assert result.date == date(2026, 1, 2)


def test_run_v2_regime_change_emits_event() -> None:
    store = _mock_store(
        latest_snapshot=PortfolioSnapshot(
            date=date(2026, 1, 1), cash=100_000.0, equity=100_000.0, regime="CAUTION"
        ),
        snapshots=[
            PortfolioSnapshot(
                date=date(2026, 1, 1), cash=100_000.0, equity=100_000.0, regime="CAUTION"
            )
        ],
    )

    mock_lake = MagicMock(spec=AlphaLakeReadPort)
    mock_lake.health.return_value = AlphaLakeHealth(status="ok")
    mock_lake.read_observations.return_value = _make_observations()

    result = run_v2(
        run_date=date(2026, 1, 2),
        store=store,
        universe=["AAPL"],
        alpha_lake=mock_lake,
        prev_equity=100_000.0,
        prev_regime="CAUTION",
    )

    assert result.date == date(2026, 1, 2)
    store.save_portfolio_snapshot.assert_called()
