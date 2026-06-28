"""Risk query service — dashboard data for the redesigned Risk Desk.

Uses the real RiskEngine (WS1-WS10) for all computations.
"""

from __future__ import annotations

from alpha_quant.application.risk import RiskEngine


class RiskService:
    def summary(self, book_id: str | None = None) -> dict[str, object]:
        engine = RiskEngine()
        return engine.run(book_id)

    def halt_state(self) -> dict[str, object]:
        engine = RiskEngine()
        result = engine.run()
        return {
            "halted": result.get("halted", False),
            "halt": result.get("halt"),
            "recent_transitions": [],
        }
