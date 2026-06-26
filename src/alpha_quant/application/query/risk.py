from __future__ import annotations

from uuid import UUID

from alpha_quant.application.query.shared import with_uow, DEFAULT_BOOK_ID


class RiskService:
    def summary(self, book_id: str | None = None) -> dict[str, object]:
        bid = UUID(book_id) if book_id else DEFAULT_BOOK_ID

        def _query(uow):
            halt = uow.store.current_halt(bid)
            positions = uow.store.list_positions(bid)
            runs = uow.store.list_decision_runs(bid, limit=1)
            near_stop = []
            for p in positions:
                stop = float(p.stop_price) if p.stop_price else None
                current = float(p.current_price) if p.current_price else None
                if stop and current and stop > 0:
                    dist = (current - stop) / current * 100
                    if dist < 5:
                        near_stop.append(
                            {
                                "symbol": p.symbol,
                                "dist_to_stop_pct": round(dist, 2),
                            }
                        )
            return {
                "halted": halt is not None and halt.halted,
                "halt": {
                    "reason": halt.reason.value if halt and halt.reason else None,
                    "details": halt.details,
                    "halted_at": str(halt.halted_at) if halt else None,
                }
                if halt
                else None,
                "positions_count": len(positions),
                "near_stop": near_stop,
                "recent_risk_events": [],
            }

        return with_uow(_query)

    def halt_state(self) -> dict[str, object]:
        bid = DEFAULT_BOOK_ID

        def _query(uow):
            halt = uow.store.current_halt(bid)
            return {
                "halted": halt is not None and halt.halted,
                "halt": {
                    "reason": halt.reason.value if halt and halt.reason else None,
                    "details": halt.details,
                    "halted_at": str(halt.halted_at) if halt else None,
                }
                if halt
                else None,
                "recent_transitions": [],
            }

        return with_uow(_query)
