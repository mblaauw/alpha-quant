"""Unit tests for ask command (domain.ask)."""

from datetime import UTC, datetime

from alpha_quant.domain.ask import extract_symbol, format_blocked_answer, is_concept_query
from alpha_quant.domain.events import CandidateBlocked


def _blocked(
    symbol: str,
    day: int = 11,
    gate: str = "ranking",
    reason: str = "low score",
) -> CandidateBlocked:
    return CandidateBlocked(
        event_id=f"evt-{symbol}",
        timestamp=datetime(2026, 6, day, 12, 0, 0, tzinfo=UTC),
        run_id="run-001",
        source="pipeline",
        symbol=symbol,
        reason=reason,
        gate=gate,
    )


class TestExtractSymbol:
    def test_extracts_uppercase_symbol(self) -> None:
        assert extract_symbol("why not TSLA?") == "TSLA"

    def test_returns_none_without_symbol(self) -> None:
        assert extract_symbol("how are things going today?") is None

    def test_ignores_common_words(self) -> None:
        assert extract_symbol("what is THE ATR?") == "ATR"

    def test_extracts_from_middle(self) -> None:
        assert extract_symbol("why did AAPL drop yesterday?") == "AAPL"


class TestIsConceptQuery:
    def test_what_is(self) -> None:
        assert is_concept_query("what is ATR") is True

    def test_explain(self) -> None:
        assert is_concept_query("explain drawdown") is True

    def test_not_a_concept_query(self) -> None:
        assert is_concept_query("why not TSLA?") is False

    def test_tell_me_about(self) -> None:
        assert is_concept_query("tell me about regime") is True


class TestFormatBlockedAnswer:
    def test_no_events(self) -> None:
        result = format_blocked_answer("TSLA", [])
        assert "No record" in result
        assert "TSLA" in result

    def test_single_event(self) -> None:
        events = [_blocked("TSLA", gate="ranking", reason="low score")]
        result = format_blocked_answer("TSLA", events)
        assert "TSLA" in result
        assert "low score" in result
        assert "gate=ranking" in result

    def test_multiple_events(self) -> None:
        events = [
            _blocked("TSLA", day=10, reason="rsi nan"),
            _blocked("TSLA", day=11, reason="low composite"),
        ]
        result = format_blocked_answer("TSLA", events, days=30)
        assert "2 time(s)" in result
        assert "rsi nan" in result
        assert "low composite" in result
