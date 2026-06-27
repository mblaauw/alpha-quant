from __future__ import annotations

from alpha_quant.application.daily_cycle import DailyCycleResult, DailyCycleService


class TestDailyCycleService:
    def test_class_exists(self) -> None:
        assert DailyCycleService is not None

    def test_result_dataclass(self) -> None:
        from uuid import UUID

        r = DailyCycleResult(
            decision_run_id=UUID("00000000-0000-0000-0000-000000000001"),
            run_key="test",
            scorecard_count=0,
            decisions=[],
            fills=[],
            events=[],
        )
        assert r.run_key == "test"
        assert r.scorecard_count == 0
        assert r.halted is False
        assert r.regime == "RISK_ON"
