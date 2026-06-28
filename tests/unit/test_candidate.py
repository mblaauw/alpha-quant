from datetime import date
from typing import Any, cast

import pytest
from pydantic import ValidationError

from alpha_quant.domain.models import Candidate


class TestCandidate:
    def test_create_valid_candidate(self) -> None:
        c = Candidate(
            symbol="AAPL",
            date=date(2026, 6, 11),
            scores={"technical": 0.8, "momentum": 0.6},
            composite_score=0.72,
            regime="RISK_ON",
            gate_results={"m1": True, "m4": True},
        )
        assert c.symbol == "AAPL"
        assert c.composite_score == 0.72
        assert c.regime == "RISK_ON"

    def test_frozen_immutability(self) -> None:
        c = Candidate(
            symbol="MSFT",
            date=date(2026, 6, 11),
            scores={},
            composite_score=0.0,
            regime="CAUTION",
            gate_results={},
        )
        with pytest.raises(ValidationError):
            c.symbol = "GOOGL"

    def test_block_reason_optional(self) -> None:
        c = Candidate(
            symbol="AAPL",
            date=date(2026, 6, 11),
            scores={},
            composite_score=0.0,
            regime="RISK_OFF",
            gate_results={},
        )
        assert c.block_reason is None

    def test_block_reason_provided(self) -> None:
        c = Candidate(
            symbol="TSLA",
            date=date(2026, 6, 11),
            scores={},
            composite_score=0.0,
            regime="RISK_OFF",
            gate_results={"m1": False},
            block_reason="Price below $5 threshold",
        )
        assert c.block_reason == "Price below $5 threshold"

    def test_scores_dict_accepts_multiple_entries(self) -> None:
        c = Candidate(
            symbol="NVDA",
            date=date(2026, 6, 11),
            scores={"technical": 0.9, "momentum": 0.85, "insider": 0.0},
            composite_score=0.72,
            regime="RISK_ON",
            gate_results={"m1": True, "m4": True, "m6": True},
        )
        assert len(c.scores) == 3
        assert c.scores["technical"] == 0.9

    def test_missing_required_fields_raises_error(self) -> None:
        candidate_model = cast(Any, Candidate)
        with pytest.raises(ValidationError):
            candidate_model(
                symbol="AAPL",
                date=date(2026, 6, 11),
            )
