"""Unit tests for daily journal generator (domain.journal)."""

from datetime import date

from alpha_quant.domain.journal import JournalEntry, generate_journal
from alpha_quant.domain.narration import NarrationContext, PositionNarration


def _ctx(
    regime: str = "RISK_ON",
    scored: int = 5,
    blocked: int = 1,
    promoted: int = 2,
    equity: float = 100_000.0,
    cash: float = 80_000.0,
    positions: list[PositionNarration] | None = None,
    concept: str | None = None,
) -> NarrationContext:
    return NarrationContext(
        date=date(2026, 6, 11),
        regime=regime,
        data_health={
            "bars": True,
            "fundamentals": True,
            "insider_tx": True,
            "attention": True,
        },
        candidates_scored=scored,
        candidates_blocked=blocked,
        candidates_promoted=promoted,
        positions=positions or [],
        equity=equity,
        cash=cash,
        concept_of_day=concept,
    )


class TestGenerateJournal:
    def test_returns_journal_entry(self) -> None:
        entry = generate_journal(_ctx())
        assert isinstance(entry, JournalEntry)
        assert entry.date == date(2026, 6, 11)

    def test_contains_regime(self) -> None:
        entry = generate_journal(_ctx(regime="RISK_OFF"))
        assert "RISK_OFF" in entry.content

    def test_contains_equity_and_cash(self) -> None:
        entry = generate_journal(_ctx(equity=100_000.0, cash=80_000.0))
        assert "100,000" in entry.content
        assert "80,000" in entry.content

    def test_contains_candidate_counts(self) -> None:
        entry = generate_journal(_ctx(scored=5, blocked=2, promoted=3))
        assert "**3** new positions" in entry.content

    def test_no_new_positions_message(self) -> None:
        entry = generate_journal(_ctx(promoted=0))
        assert "No new positions" in entry.content

    def test_risk_map_with_positions(self) -> None:
        pn = PositionNarration(
            symbol="AAPL",
            shares=100.0,
            entry_price=150.0,
            current_price=155.0,
            avg_cost=150.0,
            unrealized_pl=500.0,
            stop_price=140.0,
            risk_pct=10.0,
        )
        entry = generate_journal(_ctx(positions=[pn]))
        assert "AAPL" in entry.content
        assert "| AAPL |" in entry.content

    def test_risk_map_empty(self) -> None:
        entry = generate_journal(_ctx(positions=[]))
        assert "No open positions" in entry.content

    def test_concept_of_day(self) -> None:
        entry = generate_journal(_ctx(concept="moving averages"))
        assert "moving averages" in entry.content

    def test_concept_none(self) -> None:
        entry = generate_journal(_ctx(concept=None))
        assert "No concept selected" in entry.content

    def test_negative_space_narration(self) -> None:
        entry = generate_journal(_ctx(scored=0))
        assert "No candidates passed" in entry.content

    def test_negative_space_cash(self) -> None:
        entry = generate_journal(_ctx(cash=99_000.0, equity=100_000.0))
        assert "Mostly in cash" in entry.content

    def test_data_health_all_healthy(self) -> None:
        entry = generate_journal(_ctx())
        assert "All data sources healthy" in entry.content

    def test_frozen_model(self) -> None:
        import pytest
        from pydantic import ValidationError

        entry = generate_journal(_ctx())
        with pytest.raises(ValidationError):
            entry.content = "modified"
