"""CanonicalStore — DuckDB-backed state store.

Source-data Persistence (bars, fundamentals, insider, mentions, earnings)
has been removed — all analytical reads now go through Alpha-Lake.
"""

from .state import CanonicalStore

__all__ = ["CanonicalStore"]
