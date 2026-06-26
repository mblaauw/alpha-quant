from __future__ import annotations

from alpha_quant.application.query.shared import DEFAULT_BOOK_ID, with_uow


class CommandCenterService:
    def summary(self) -> dict[str, object]:
        book_id = DEFAULT_BOOK_ID

        def _query(uow):
            uow.store.list_strategies()
            halt = uow.store.current_halt(book_id)
            runs = uow.store.list_decision_runs(book_id, limit=1)
            candidates = []
            if runs:
                run = runs[0]
                candidates = uow.store.list_candidates(run.decision_run_id, limit=20)
            positions = uow.store.list_positions(book_id)
            portfolio = uow.store.load_portfolio(book_id)
            return {
                "last_run": {
                    "run_id": str(runs[0].decision_run_id) if runs else None,
                    "status": runs[0].status.value if runs else None,
                    "started_at": str(runs[0].started_at) if runs else None,
                }
                if runs
                else None,
                "pending_commands": 0,
                "positions_count": len(positions),
                "portfolio": {
                    "cash": float(portfolio.cash),
                    "equity": float(portfolio.cash)
                    + sum(float(p.market_value or 0) for p in portfolio.positions),
                    "market_value": sum(float(p.market_value or 0) for p in portfolio.positions),
                }
                if portfolio
                else None,
                "halted": halt is not None and halt.halted,
                "halt": halt,
                "recent_decisions": candidates,
            }

        return with_uow(_query)

    def readiness(self) -> dict[str, object]:
        book_id = DEFAULT_BOOK_ID

        def _query(uow):
            halt = uow.store.current_halt(book_id)
            runs = uow.store.list_decision_runs(book_id, limit=1)
            return {
                "halted": halt is not None and halt.halted,
                "halt_reason": halt.reason.value if halt and halt.reason else None,
                "last_run_status": runs[0].status.value if runs else None,
            }

        return with_uow(_query)
