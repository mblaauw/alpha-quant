from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from alpha_quant.adapters.postgres.operational_store import PostgresOperationalStore


class OperationalUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._store: PostgresOperationalStore | None = None

    @property
    def session(self) -> Session:
        if self._session is None:
            msg = "Unit of work session is only available inside its context manager"
            raise RuntimeError(msg)
        return self._session

    @property
    def store(self) -> PostgresOperationalStore:
        if self._store is None:
            msg = "Unit of work store is only available inside its context manager"
            raise RuntimeError(msg)
        return self._store

    def __enter__(self) -> OperationalUnitOfWork:
        self._session = self._session_factory()
        self._store = PostgresOperationalStore(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        if exc_type is not None:
            self._session.rollback()
        else:
            self._session.commit()
        self._session.close()
        self._session = None
        self._store = None
