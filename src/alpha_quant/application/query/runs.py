from __future__ import annotations

from uuid import UUID

from alpha_quant.application.query.shared import with_uow, DEFAULT_BOOK_ID


class RunService:
    def list_runs(
        self,
        book_id: str | None = None,
        run_type: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        bid = UUID(book_id) if book_id else DEFAULT_BOOK_ID

        def _query(uow):
            runs = uow.store.list_decision_runs(bid, limit=limit)
            items = [
                {
                    "run_id": str(r.decision_run_id),
                    "run_key": r.run_key,
                    "run_kind": r.run_kind.value,
                    "status": r.status.value,
                    "started_at": str(r.started_at) if r.started_at else None,
                    "completed_at": str(r.completed_at) if r.completed_at else None,
                    "decision_as_of": str(r.decision_as_of) if r.decision_as_of else None,
                    "failure_reason": r.failure_reason,
                }
                for r in runs
            ]
            return {"items": items, "next_cursor": None}

        return with_uow(_query)

    def get_run(self, run_id: str) -> dict[str, object] | None:
        def _query(uow):
            runs = uow.store.list_decision_runs(DEFAULT_BOOK_ID, limit=200)
            run = next((r for r in runs if str(r.decision_run_id) == run_id), None)
            if not run:
                return None
            candidates = uow.store.list_candidates(run.decision_run_id, limit=100)
            return {
                "run": {
                    "run_id": str(run.decision_run_id),
                    "run_key": run.run_key,
                    "run_kind": run.run_kind.value,
                    "status": run.status.value,
                    "started_at": str(run.started_at) if run.started_at else None,
                    "completed_at": str(run.completed_at) if run.completed_at else None,
                    "decision_as_of": str(run.decision_as_of) if run.decision_as_of else None,
                    "failure_reason": run.failure_reason,
                },
                "decisions": [
                    {
                        "symbol": c.symbol,
                        "composite_score": float(c.composite_score) if c.composite_score else None,
                        "blocked": c.blocked,
                        "block_reason": c.block_reason,
                    }
                    for c in candidates
                ],
                "commands": [],
            }

        return with_uow(_query)
