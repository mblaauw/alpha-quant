from __future__ import annotations

from uuid import UUID

from alpha_quant.application.query.shared import (
    resolve_active_book_id,
    with_uow,
)

_M_CATEGORY = {
    "Universe": ("M1", "hard"),
    "Universe & Investability": ("M1", "hard"),
    "Regime": ("M2", "soft"),
    "Market Regime": ("M2", "soft"),
    "Technical": ("M3", "score"),
    "Technical Trend": ("M3", "score"),
    "Fundamental": ("M4", "soft"),
    "Fundamental Resilience": ("M4", "soft"),
    "Insider": ("M5", "evidence"),
    "Insider Behaviour": ("M5", "evidence"),
    "Attention": ("M6", "soft"),
    "Crowding": ("M6", "soft"),
    "Event Risk": ("M7", "hard"),
    "Known Event": ("M7", "hard"),
    "Rank": ("M8", "score"),
    "Ranking": ("M8", "score"),
}
_M_NAMES = {
    "M1": "Universe & investability",
    "M2": "Market regime & posture",
    "M3": "Technical state & leadership",
    "M4": "Fundamental resilience",
    "M5": "Insider behaviour",
    "M6": "Crowding & attention",
    "M7": "Known event & gap risk",
    "M8": "Rank & selection",
}
_M_QUESTIONS = {
    "M1": "Can this security be traded?",
    "M2": "Should long risk be deployed?",
    "M3": "Is it a leader with a valid setup now?",
    "M4": "Is there a fundamental reason to avoid it?",
    "M5": "Is insider activity supportive?",
    "M6": "Is attention making the entry unsafe?",
    "M7": "Is event risk too large for normal risk controls?",
    "M8": "Is this the best remaining use of risk budget?",
}


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
        bid = UUID(book_id) if book_id else resolve_active_book_id()

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
            runs = uow.store.list_decision_runs(resolve_active_book_id(), limit=1)
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
            policies = [
                {
                    "policy_name": e.policy_name,
                    "policy_version": e.policy_version,
                    "score": float(e.score) if e.score else None,
                    "passed": e.passed,
                    "reason": e.reason,
                }
                for e in filtered_evals
            ]
            modules = [self._policy_to_module(p) for p in policies]
            action = "BLOCKED" if candidate.blocked else "ELIGIBLE"
            sev = "bad" if candidate.blocked else "ok"
            narrative = {
                "severity": sev,
                "text": f"{action}: {candidate.symbol} — "
                f"score {candidate.composite_score:.2f if candidate.composite_score else 'N/A'}, "
                f"reason: {candidate.block_reason or 'passes all gates'}.",
            }
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
                "policies": policies,
                "modules": modules,
                "narrative": narrative,
                "position_now": None,
                "open_risk": None,
            }

        return with_uow(_query)

    @staticmethod
    def _policy_to_module(p: dict[str, object]) -> dict[str, object]:
        name = str(p.get("policy_name", ""))
        mid, mtype = _M_CATEGORY.get(name, ("", "score"))
        passed = p.get("passed", True) is True
        state_tone = "ok" if passed else "bad"
        score_val = p.get("score")
        return {
            "id": mid,
            "name": _M_NAMES.get(mid, name),
            "type": mtype,
            "question": _M_QUESTIONS.get(mid, ""),
            "state": "PASS" if passed else "FAIL",
            "state_tone": state_tone,
            "score": round(float(score_val), 2) if score_val is not None else None,  # ty: ignore
            "archetype": None,
            "metrics": [],
            "reason": str(p.get("reason", "")),
        }
