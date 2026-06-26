from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from alpha_quant.adapters.postgres.operational_store import PostgresOperationalStore


class OperationalUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None
        self.store: PostgresOperationalStore | None = None

    def __enter__(self) -> OperationalUnitOfWork:
        self.session = self._session_factory()
        self.store = PostgresOperationalStore(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        if exc_type is not None:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()
        self.session = None
        self.store = None
