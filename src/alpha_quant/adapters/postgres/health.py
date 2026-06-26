from __future__ import annotations

from sqlalchemy import text


def health_check(engine) -> dict[str, object]:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS ok"))
            row = result.one()
            db_ok = row._mapping["ok"] == 1
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "db": False}
    return {"status": "healthy", "db": db_ok}
