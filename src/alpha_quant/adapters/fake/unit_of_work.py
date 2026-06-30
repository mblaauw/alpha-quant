from __future__ import annotations

from types import TracebackType

from alpha_quant.adapters.fake.operational_store import FakeOperationalStore


class FakeUnitOfWork:
    def __init__(self, store: FakeOperationalStore | None = None) -> None:
        self._store: FakeOperationalStore | None = None
        self._seed_store = store

    @property
    def store(self) -> FakeOperationalStore:
        if self._store is None:
            msg = "Unit of work store is only available inside its context manager"
            raise RuntimeError(msg)
        return self._store

    def __enter__(self) -> FakeUnitOfWork:
        self._store = self._seed_store or FakeOperationalStore()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._store = None
