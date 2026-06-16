"""CanonicalStore — DuckDB-backed state store with Parquet analytical layer.

Split from app/store.py into:
  - store/state.py     — CanonicalStore class + DuckDB state operations
  - store/canonical.py — Parquet dataset write/read helpers
  - store/schema.py    — Schemas, model serialization, partition helpers

Same public API: from app.store import CanonicalStore
"""

from .state import CanonicalStore

__all__ = ["CanonicalStore"]
