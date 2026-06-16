"""Unit tests for M8 composite ranking (domain.ranking)."""

from datetime import date

from domain.models import Candidate
from domain.ranking import rank


def _candidate(
    symbol: str,
    technical: float = 0.6,
    momentum: float = 0.6,
    insider: float | None = None,
    blocked: bool = False,
) -> Candidate:
    scores: dict[str, float] = {"technical": technical, "momentum": momentum}
    if insider is not None:
        scores["insider"] = insider
    return Candidate(
        symbol=symbol,
        date=date(2026, 6, 11),
        scores=scores,
        composite_score=0.0,
        regime="RISK_ON",
        gate_results={"m1": not blocked, "m4": True},
        block_reason="blocked" if blocked else None,
    )


class TestRank:
    def test_empty_candidates_returns_empty(self) -> None:
        result = rank([], max_positions=10, current_count=0)
        assert result == []

    def test_no_slots_returns_empty(self) -> None:
        c = _candidate("AAPL")
        result = rank([c], max_positions=10, current_count=10)
        assert result == []

    def test_excludes_blocked_candidates(self) -> None:
        c1 = _candidate("AAPL")
        c2 = _candidate("MSFT", blocked=True)
        result = rank([c1, c2], max_positions=10, current_count=0)
        assert c1.symbol in {c.symbol for c in result}
        assert c2.symbol not in {c.symbol for c in result}

    def test_excludes_candidate_with_false_gate(self) -> None:
        c1 = _candidate("AAPL")
        c2 = _candidate("MSFT").model_copy(
            update={"gate_results": {"m1": False, "m4": True}},
        )
        result = rank([c1, c2], max_positions=10, current_count=0)
        assert c1.symbol in {c.symbol for c in result}
        assert c2.symbol not in {c.symbol for c in result}

    def test_sort_by_composite_score_descending(self) -> None:
        c1 = _candidate("AAPL", technical=0.9, momentum=0.9)
        c2 = _candidate("MSFT", technical=0.7, momentum=0.7)
        c3 = _candidate("GOOGL", technical=0.8, momentum=0.8)
        result = rank([c1, c2, c3], max_positions=10, current_count=0)
        assert [c.symbol for c in result] == ["AAPL", "GOOGL", "MSFT"]

    def test_respects_max_positions(self) -> None:
        c1 = _candidate("AAPL", technical=0.9, momentum=0.9)
        c2 = _candidate("MSFT", technical=0.8, momentum=0.8)
        c3 = _candidate("GOOGL", technical=0.7, momentum=0.7)
        result = rank([c1, c2, c3], max_positions=2, current_count=0)
        assert len(result) == 2

    def test_respects_current_count(self) -> None:
        c1 = _candidate("AAPL", technical=0.9, momentum=0.9)
        c2 = _candidate("MSFT", technical=0.8, momentum=0.8)
        result = rank([c1, c2], max_positions=3, current_count=2)
        assert len(result) == 1

    def test_adv_tiebreak(self) -> None:
        c1 = _candidate("AAPL", technical=0.9, momentum=0.9)
        c2 = _candidate("MSFT", technical=0.9, momentum=0.9)
        adv = {"AAPL": 50_000_000, "MSFT": 100_000_000}
        result = rank([c1, c2], max_positions=10, current_count=0, symbol_adv=adv)
        assert result[0].symbol == "MSFT"
        assert result[1].symbol == "AAPL"

    def test_above_threshold_only(self) -> None:
        c1 = _candidate("AAPL", technical=0.6, momentum=0.6)
        c2 = _candidate("MSFT", technical=0.3, momentum=0.3)
        result = rank([c1, c2], max_positions=10, current_count=0)
        result_symbols = {c.symbol for c in result}
        assert "AAPL" in result_symbols
        assert "MSFT" not in result_symbols

    def test_insider_weighting(self) -> None:
        c = _candidate("AAPL", technical=0.8, momentum=0.5, insider=0.7)
        result = rank([c], max_positions=10, current_count=0)
        assert result
        assert 0.5 < result[0].composite_score <= 1.0

    def test_no_insider_weighting(self) -> None:
        c = _candidate("AAPL", technical=0.8, momentum=0.5)
        result = rank([c], max_positions=10, current_count=0)
        assert result
        assert 0.5 < result[0].composite_score <= 1.0

    def test_sector_concentration_limit(self) -> None:
        c1 = _candidate("AAPL", technical=0.9, momentum=0.9)
        c2 = _candidate("MSFT", technical=0.8, momentum=0.8)
        c3 = _candidate("GOOGL", technical=0.7, momentum=0.7)
        sector_map = {"AAPL": "tech", "MSFT": "tech", "GOOGL": "tech"}
        result = rank(
            [c1, c2, c3],
            max_positions=10,
            current_count=0,
            sector_map=sector_map,
            max_sector_pct=0.25,
        )
        # 10 slots * 0.25 = max 2 per sector, so should cap at 2
        assert len(result) <= 2
