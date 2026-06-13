"""Unit tests for fact-checker (alpha_quant.domain.fact_check)."""

from datetime import date

from alpha_quant.domain.fact_check import render_template, verify
from alpha_quant.domain.narration import NarrationContext


def _ctx(**overrides: object) -> NarrationContext:
    data: dict = {
        "date": date(2026, 6, 11),
        "regime": "RISK_ON",
        "data_health": {"eodhd": True, "alpaca": True},
        "candidates_scored": 5,
        "candidates_blocked": 1,
        "candidates_promoted": 2,
        "positions": [],
        "equity": 100_000.0,
        "cash": 80_000.0,
        "concept_of_day": None,
    }
    data.update(overrides)
    return NarrationContext(**data)


class TestVerify:
    def test_passes_when_numbers_match(self) -> None:
        ctx = _ctx(candidates_scored=5)
        assert verify("We scored 5 candidates today.", ctx) is True

    def test_fails_on_hallucinated_number(self) -> None:
        ctx = _ctx(candidates_scored=3)
        assert verify("We scored 99 candidates today.", ctx) is False

    def test_passes_with_multiple_valid_numbers(self) -> None:
        ctx = _ctx(candidates_scored=5, candidates_blocked=1, equity=100_000.0)
        result = verify("Scored 5, blocked 1, equity 100000.", ctx)
        assert result is True

    def test_fails_with_any_hallucinated_number(self) -> None:
        ctx = _ctx(candidates_scored=5, cash=80_000.0)
        result = verify("Scored 5, cash 999999.", ctx)
        assert result is False

    def test_passes_with_decimal_numbers(self) -> None:
        ctx = _ctx(equity=100_000.0, cash=80_000.0)
        result = verify("Equity: 100000.00, Cash: 80000.00", ctx)
        assert result is True

    def test_passes_with_integer_variants(self) -> None:
        ctx = _ctx(equity=100_000.0)
        result = verify("Equity is 100000.", ctx)
        assert result is True

    def test_empty_output_passes(self) -> None:
        ctx = _ctx()
        assert verify("", ctx) is True

    def test_no_numbers_in_output_passes(self) -> None:
        ctx = _ctx()
        assert verify("The market looks good today.", ctx) is True


class TestRenderTemplate:
    def test_renders_all_fields(self) -> None:
        ctx = _ctx(concept_of_day="moving averages")
        result = render_template(ctx)
        assert "2026-06-11" in result
        assert "RISK_ON" in result
        assert "100,000" in result
        assert "80,000" in result
        import re

        assert re.search(r"\b5\b", result)
        assert re.search(r"\b2\b", result)
        assert "moving averages" in result

    def test_concept_none_shows_fallback(self) -> None:
        ctx = _ctx(concept_of_day=None)
        result = render_template(ctx)
        assert "No concept selected" in result or "none" in result

    def test_position_count(self) -> None:
        from alpha_quant.domain.narration import PositionNarration

        ctx = _ctx(
            positions=[
                PositionNarration(
                    symbol="AAPL",
                    shares=100.0,
                    entry_price=150.0,
                    current_price=155.0,
                    avg_cost=150.0,
                    unrealized_pl=500.0,
                    stop_price=140.0,
                    risk_pct=10.0,
                ),
            ],
        )
        result = render_template(ctx)
        assert "Open positions: 1" in result
