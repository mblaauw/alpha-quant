"""CanonicalStore — DuckDB-backed state store with Parquet analytical layer.

Split from app/store.py into:
  - store/state.py     — CanonicalStore class + DuckDB state operations
  - store/canonical.py — Parquet dataset write/read helpers
  - store/schema.py    — Schemas, model serialization, partition helpers

Same public API: from alpha_quant.app.store import CanonicalStore
"""

from alpha_quant.app.store.state import CanonicalStore

__all__ = ["CanonicalStore"]
