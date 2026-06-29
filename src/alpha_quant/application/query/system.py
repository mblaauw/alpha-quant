from __future__ import annotations

from alpha_quant.application.query.shared import with_uow


_PG_ENGINE: object | None = None


def _get_pg_engine():
    global _PG_ENGINE
    if _PG_ENGINE is None:
        import os as _os

        from alpha_quant.adapters.postgres.engine import create_engine

        _PG_ENGINE = create_engine(
            database_url=_os.environ.get(
                "DATABASE_URL",
                "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant",
            )
        )
    return _PG_ENGINE


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
    from alpha_quant.application.query.shared import resolve_active_book_id

    return str(resolve_active_book_id())


def _check_postgres_health() -> bool:
    try:
        from alpha_quant.adapters.postgres.health import health_check

        result = health_check(_get_pg_engine())
        return bool(result.get("db", result.get("database", False)))
    except Exception:
        return False


MOCK_BOOK_ID = "00000000-0000-0000-0000-000000000002"


class SystemService:
    def _mock_mode(self) -> bool:
        def _query(uow):
            val = uow.store.config_get("mock_mode", "false")
            return val == "true"

        return with_uow(_query)

    def context(self) -> dict[str, object]:
        mock_mode = self._mock_mode()
        live_book_id = _resolve_book_id()
        book_id = MOCK_BOOK_ID if mock_mode else live_book_id
        db_healthy = _check_postgres_health()
        lake_healthy = _check_lake_health()

        def _query(uow):
            halt = uow.store.current_halt(book_id)
            active_halt = halt if halt is not None and halt.halted else None
            runs = uow.store.list_decision_runs(book_id, limit=1)
            run = runs[0] if runs else None
            books = uow.store.list_books()
            return {
                "halted": active_halt is not None,
                "halt_reason": active_halt.reason.value
                if active_halt and active_halt.reason
                else None,
                "last_run_id": str(run.decision_run_id) if run else None,
                "last_run_status": run.status.value if run else None,
                "last_run_as_of": str(run.decision_as_of) if run and run.decision_as_of else None,
                "active_book_id": str(book_id),
                "books": [
                    {
                        "book_id": str(b.book_id),
                        "label": b.name,
                        "mode": b.kind,
                        "policy": "full",
                    }
                    for b in books
                ],
                "mode": "PAPER",
                "snapshot": None,
                "mock_mode": mock_mode,
                "lake_healthy": lake_healthy,
                "postgres_healthy": db_healthy,
            }

        return with_uow(_query)

    def set_mock_mode(self, mock: bool) -> None:
        def _query(uow):
            uow.store.config_set("mock_mode", "true" if mock else "false")

        with_uow(_query)

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
