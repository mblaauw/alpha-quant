from __future__ import annotations

from alpha_quant.application.query.shared import with_uow


def _check_lake_health() -> bool:
    try:
        from alpha_quant.application.config import load_config
        from alpha_quant.application.factory import create_alpha_lake_reader

        config = load_config()
        lake = create_alpha_lake_reader(config)
        health = lake.health()
        lake.close()
        return health.status == "ok"
    except Exception:
        return False


def _resolve_book_id() -> str:
    try:
        from alpha_quant.application.query.shared import DEFAULT_BOOK_ID

        return str(DEFAULT_BOOK_ID)
    except Exception:
        return "00000000-0000-0000-0000-000000000001"


def _check_postgres_health() -> bool:
    try:
        from alpha_quant.adapters.postgres.engine import create_engine
        from alpha_quant.adapters.postgres.health import health_check

        engine = create_engine()
        result = health_check(engine)
        return bool(result.get("database", False))
    except Exception:
        return False


class SystemService:
    def context(self) -> dict[str, object]:
        book_id = _resolve_book_id()
        db_healthy = _check_postgres_health()
        lake_healthy = _check_lake_health()

        def _query(uow):
            halt = uow.store.current_halt(book_id)
            runs = uow.store.list_decision_runs(book_id, limit=1)
            run = runs[0] if runs else None
            books = uow.store.list_books()
            return {
                "halted": halt is not None and halt.halted,
                "halt_reason": halt.reason.value if halt and halt.reason else None,
                "last_run_id": str(run.decision_run_id) if run else None,
                "last_run_status": run.status.value if run else None,
                "last_run_as_of": str(run.decision_as_of) if run and run.decision_as_of else None,
                "active_book_id": str(book_id),
                "books": [{"id": str(b.book_id), "name": b.name, "kind": b.kind} for b in books],
                "mode": "PAPER",
                "snapshot": None,
                "lake_healthy": lake_healthy,
                "postgres_healthy": db_healthy,
            }

        return with_uow(_query)

    def health(self) -> dict[str, object]:
        pg_h = _check_postgres_health()
        lake_h = _check_lake_health()
        return {
            "components": {
                "postgresql": {
                    "healthy": pg_h,
                    "status": "connected" if pg_h else "disconnected",
                    "detail": "PostgreSQL operational store",
                },
                "alpha_lake": {
                    "healthy": lake_h,
                    "status": "connected" if lake_h else "disconnected",
                    "detail": "Market facts / readouts / facts-bundle API",
                },
                "operational": {
                    "healthy": True,
                    "status": "running",
                    "detail": "Command worker + API",
                },
            },
        }

    def full_status(self) -> dict[str, object]:
        ctx = self.context()
        health = self.health()
        return {
            **ctx,
            **health,
        }
