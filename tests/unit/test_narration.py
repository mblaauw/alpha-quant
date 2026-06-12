"""Unit tests for narration context builder (alpha_quant.domain.narration)."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from alpha_quant.domain.events import (
    CandidateBlocked,
    CandidatePromoted,
    CandidateScored,
    SourceDegraded,
)
from alpha_quant.domain.models import Position
from alpha_quant.domain.narration import PositionNarration, build


def _event(**kwargs: object) -> dict:
    base = {
        "event_id": "evt-001",
        "timestamp": datetime(2026, 6, 11, 12, 0, 0),
        "run_id": "run-001",
        "source": "pipeline",
    }
    base.update(**kwargs)
    return base


class TestBuild:
    def test_counts_events(self) -> None:
        events = [
            CandidateScored(
                **{**_event(), "symbol": "AAPL", "composite_score": 0.8, "components": {}}
            ),
            CandidateScored(
                **{
                    **_event(event_id="evt-002"),
                    "symbol": "MSFT",
                    "composite_score": 0.7,
                    "components": {},
                }
            ),
            CandidateBlocked(
                **{
                    **_event(event_id="evt-003"),
                    "symbol": "GOOGL",
                    "reason": "low",
                    "gate": "ranking",
                }
            ),
            CandidatePromoted(
                **{
                    **_event(event_id="evt-004"),
                    "symbol": "AAPL",
                    "score": 0.8,
                    "target_weight": 0.05,
                }
            ),
        ]
        ctx = build(
            run_date=date(2026, 6, 11),
            events=events,
            positions=[],
            equity=100_000.0,
            cash=90_000.0,
            regime="RISK_ON",
        )
        assert ctx.candidates_scored == 2
        assert ctx.candidates_blocked == 1
        assert ctx.candidates_promoted == 1

    def test_data_health_from_degraded_events(self) -> None:
        events = [
            SourceDegraded(
                **{
                    **_event(),
                    "source_name": "openinsider",
                    "fallback": "skip",
                }
            ),
        ]
        ctx = build(
            run_date=date(2026, 6, 11),
            events=events,
            positions=[],
            equity=100_000.0,
            cash=90_000.0,
            regime="CAUTION",
        )
        assert ctx.data_health["openinsider"] is False
        assert ctx.data_health["eodhd"] is True
        assert ctx.data_health["reddit"] is True

    def test_positions_included(self) -> None:
        positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                entry_price=150.0,
                avg_cost=150.0,
                current_price=155.0,
                stop_price=140.0,
                market_value=15_500.0,
                unrealized_pl=500.0,
            ),
        ]
        ctx = build(
            run_date=date(2026, 6, 11),
            events=[],
            positions=positions,
            equity=100_000.0,
            cash=84_500.0,
            regime="RISK_ON",
        )
        assert len(ctx.positions) == 1
        pn = ctx.positions[0]
        assert pn.symbol == "AAPL"
        assert pn.shares == 100.0
        assert pn.unrealized_pl == 500.0

    def test_risk_map_calculation(self) -> None:
        positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                entry_price=100.0,
                avg_cost=100.0,
                current_price=105.0,
                stop_price=95.0,
                market_value=10_500.0,
            ),
        ]
        ctx = build(
            run_date=date(2026, 6, 11),
            events=[],
            positions=positions,
            equity=50_000.0,
            cash=39_500.0,
            regime="RISK_ON",
        )
        pn = ctx.positions[0]
        assert pn.risk_pct is not None

    def test_empty_positions(self) -> None:
        ctx = build(
            run_date=date(2026, 6, 11),
            events=[],
            positions=[],
            equity=100_000.0,
            cash=100_000.0,
            regime="RISK_ON",
        )
        assert ctx.positions == []

    def test_zero_quantity_positions_excluded(self) -> None:
        positions = [
            Position(
                symbol="AAPL",
                quantity=0.0,
                entry_price=150.0,
                avg_cost=150.0,
                current_price=155.0,
                stop_price=140.0,
                market_value=0.0,
            ),
        ]
        ctx = build(
            run_date=date(2026, 6, 11),
            events=[],
            positions=positions,
            equity=100_000.0,
            cash=100_000.0,
            regime="RISK_ON",
        )
        assert ctx.positions == []

    def test_concept_of_day(self) -> None:
        ctx = build(
            run_date=date(2026, 6, 11),
            events=[],
            positions=[],
            equity=100_000.0,
            cash=100_000.0,
            regime="RISK_ON",
            concept_of_day="moving averages",
        )
        assert ctx.concept_of_day == "moving averages"

    def test_concept_of_day_default_none(self) -> None:
        ctx = build(
            run_date=date(2026, 6, 11),
            events=[],
            positions=[],
            equity=100_000.0,
            cash=100_000.0,
            regime="RISK_ON",
        )
        assert ctx.concept_of_day is None

    def test_frozen_model_immutable(self) -> None:
        ctx = build(
            run_date=date(2026, 6, 11),
            events=[],
            positions=[],
            equity=100_000.0,
            cash=100_000.0,
            regime="RISK_ON",
        )
        with pytest.raises(ValidationError):
            ctx.regime = "RISK_OFF"

    def test_rounds_equity_and_cash(self) -> None:
        ctx = build(
            run_date=date(2026, 6, 11),
            events=[],
            positions=[],
            equity=100_000.1234,
            cash=90_000.5678,
            regime="RISK_ON",
        )
        assert ctx.equity == 100_000.12
        assert ctx.cash == 90_000.57


class TestPositionNarration:
    def test_frozen(self) -> None:
        pn = PositionNarration(
            symbol="AAPL",
            shares=100.0,
            entry_price=150.0,
            current_price=155.0,
            avg_cost=150.0,
            unrealized_pl=500.0,
            stop_price=140.0,
            risk_pct=2.0,
        )
        assert pn.symbol == "AAPL"
