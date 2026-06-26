from __future__ import annotations

from uuid import UUID

from alpha_quant.application.query.shared import with_uow, DEFAULT_BOOK_ID


class DecisionService:
    def list_decisions(
        self,
        book_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        sort: str = "desc",
        symbol: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, object]:
        bid = UUID(book_id) if book_id else DEFAULT_BOOK_ID

        def _query(uow):
            if run_id:
                candidates = uow.store.list_candidates(UUID(run_id), limit=limit)
            else:
                runs = uow.store.list_decision_runs(bid, limit=1)
                candidates = []
                if runs:
                    candidates = uow.store.list_candidates(runs[0].decision_run_id, limit=limit)
            items = [
                {
                    "candidate_id": str(c.candidate_id),
                    "symbol": c.symbol,
                    "composite_score": float(c.composite_score) if c.composite_score else None,
                    "blocked": c.blocked,
                    "block_reason": c.block_reason,
                    "regime": c.regime,
                }
                for c in candidates
                if not symbol or c.symbol == symbol
            ]
            return {"items": items, "next_cursor": None}

        return with_uow(_query)

    def get_decision(self, decision_id: str) -> dict[str, object] | None:
        def _query(uow):
            runs = uow.store.list_decision_runs(DEFAULT_BOOK_ID, limit=1)
            if not runs:
                return None
            candidates = uow.store.list_candidates(runs[0].decision_run_id, limit=200)
            candidate = next(
                (
                    c
                    for c in candidates
                    if str(c.candidate_id) == decision_id or c.symbol == decision_id
                ),
                None,
            )
            if not candidate:
                return None
            evals = uow.store.list_policy_evals(runs[0].decision_run_id, limit=500)
            filtered_evals = [
                e for e in evals if str(e.candidate_id) == str(candidate.candidate_id)
            ]
            return {
                "decision": {
                    "candidate_id": str(candidate.candidate_id),
                    "symbol": candidate.symbol,
                    "composite_score": float(candidate.composite_score)
                    if candidate.composite_score
                    else None,
                    "blocked": candidate.blocked,
                    "block_reason": candidate.block_reason,
                    "regime": candidate.regime,
                    "gate_results": candidate.gate_results,
                },
                "policies": [
                    {
                        "policy_name": e.policy_name,
                        "policy_version": e.policy_version,
                        "score": float(e.score) if e.score else None,
                        "passed": e.passed,
                        "reason": e.reason,
                    }
                    for e in filtered_evals
                ],
            }

        return with_uow(_query)
