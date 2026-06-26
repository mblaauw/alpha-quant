from __future__ import annotations

from uuid import UUID

from alpha_quant.application.query.shared import with_uow, DEFAULT_BOOK_ID


class SystemService:
    def context(self) -> dict[str, object]:
        book_id = DEFAULT_BOOK_ID

        def _query(uow):
            halt = uow.store.current_halt(book_id)
            runs = uow.store.list_decision_runs(book_id, limit=1)
            run = runs[0] if runs else None
            return {
                "halted": halt is not None and halt.halted,
                "halt_reason": halt.reason.value if halt and halt.reason else None,
                "last_run_id": str(run.decision_run_id) if run else None,
                "last_run_status": run.status.value if run else None,
                "last_run_as_of": str(run.decision_as_of) if run and run.decision_as_of else None,
            }

        return with_uow(_query)

    def health(self) -> dict[str, object]:
        try:
            from alpha_quant.adapters.postgres.engine import create_engine
            from alpha_quant.adapters.postgres.health import health_check

            engine = create_engine()
            result = health_check(engine)
            db_healthy = result.get("database", False)
        except Exception:
            db_healthy = False
        return {
            "components": {
                "postgresql": {"healthy": db_healthy},
            },
        }

    def full_status(self) -> dict[str, object]:
        ctx = self.context()
        health = self.health()
        return {
            **ctx,
            **health,
        }
