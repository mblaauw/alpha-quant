from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import duckdb
import structlog

from alpha_quant.adapters.postgres import create_engine, create_session
from alpha_quant.adapters.postgres.tables import (
    AuditEvent,
    CandidateEvaluation,
    DecisionRun,
    PaperFill,
    PaperOrder,
    PolicyEvaluation,
    PortfolioBook,
    PortfolioMark,
    PositionCurrent,
    RunKind,
    RunStatus,
    SecurityReference,
    Strategy,
    StrategyVersion,
)
from alpha_quant.application.factory import DEFAULT_DATABASE_URL

logger = structlog.get_logger()

_RUN_STATUS_MAP: dict[str, RunStatus] = {
    "running": RunStatus.RUNNING,
    "completed": RunStatus.COMPLETED,
    "halted": RunStatus.HALTED,
    "violations": RunStatus.HALTED,
    "no_data": RunStatus.FAILED,
    "no_spy_data": RunStatus.FAILED,
}


def _run_kind(raw: str) -> RunKind:
    lowered = raw.lower()
    if "backtest" in lowered:
        return RunKind.BACKTEST
    if "replay" in lowered:
        return RunKind.REPLAY
    return RunKind.DAILY


class LegacyDuckDBImporter:
    def __init__(
        self,
        duckdb_path: str = "data/state.db",
        postgres_url: str = DEFAULT_DATABASE_URL,
    ) -> None:
        self._duckdb_path = duckdb_path
        self._postgres_url = postgres_url
        self._ddb: duckdb.DuckDBPyConnection | None = None
        self._session = None
        self._session_factory = None
        self._symbol_cache: dict[str, str] = {}
        self._default_book_id: str | None = None
        self._default_strategy_version_id: str | None = None

    def run(self) -> int:
        count = 0
        logger.info("import_started", duckdb_path=self._duckdb_path)

        self._ddb = duckdb.connect(self._duckdb_path)
        engine = create_engine(self._postgres_url)
        self._session_factory = create_session(engine)

        with self._session_factory() as session:
            self._session = session
            self._ensure_defaults()
            count += self._import_security_references()
            count += self._import_decision_runs()
            count += self._import_audit_events()
            count += self._import_portfolio_marks()
            count += self._import_positions()
            count += self._import_orders()
            count += self._import_fills()
            session.commit()

        self._ddb.close()
        logger.info("import_completed", total_rows=count)
        return count

    def _ensure_defaults(self) -> None:
        s = self._session
        strategy = s.query(Strategy).filter(Strategy.name == "default").first()
        if strategy is None:
            strategy = Strategy(
                strategy_id=str(uuid4()), name="default", created_at=datetime.now(UTC)
            )
            s.add(strategy)
            s.flush()

        sv = (
            s.query(StrategyVersion)
            .filter(
                StrategyVersion.strategy_id == strategy.strategy_id,
                StrategyVersion.version_label == "imported",
            )
            .first()
        )
        if sv is None:
            sv = StrategyVersion(
                strategy_version_id=str(uuid4()),
                strategy_id=strategy.strategy_id,
                version_label="imported",
                config_json="{}",
                config_hash="imported",
                created_at=datetime.now(UTC),
            )
            s.add(sv)
            s.flush()
        self._default_strategy_version_id = sv.strategy_version_id

        book = s.query(PortfolioBook).filter(PortfolioBook.name == "default").first()
        if book is None:
            book = PortfolioBook(
                book_id=str(uuid4()), name="default", kind="paper", created_at=datetime.now(UTC)
            )
            s.add(book)
            s.flush()
        self._default_book_id = book.book_id

        s.flush()

    def _ensure_security(self, symbol: str) -> str:
        cached = self._symbol_cache.get(symbol)
        if cached:
            return cached
        existing = (
            self._session.query(SecurityReference)
            .filter(SecurityReference.symbol == symbol)
            .first()
        )
        if existing:
            self._symbol_cache[symbol] = existing.security_id
            return existing.security_id
        sid = str(uuid4())
        self._session.add(
            SecurityReference(
                security_id=sid,
                symbol=symbol,
                display_name=symbol,
            )
        )
        self._session.flush()
        self._symbol_cache[symbol] = sid
        return sid

    def _import_security_references(self) -> int:
        symbols: set[str] = set()
        for table, col in [
            ("positions", "symbol"),
            ("orders", "symbol"),
            ("fills", "symbol"),
            ("decisions", "symbol"),
            ("equity_curve", "book"),
        ]:
            try:
                rows = self._ddb.execute(f'SELECT DISTINCT "{col}" FROM "{table}"').fetchall()
                for (val,) in rows:
                    if val:
                        symbols.add(str(val))
            except duckdb.CatalogException:
                continue
        count = 0
        for symbol in sorted(symbols):
            self._ensure_security(symbol)
            count += 1
        return count

    def _import_decision_runs(self) -> int:
        try:
            rows = self._ddb.execute(
                "SELECT run_id, run_type, config_hash, fixture_version,"
                " start_ts, end_ts, status, manifest_hash FROM runs ORDER BY start_ts"
            ).fetchall()
        except duckdb.CatalogException:
            return 0

        count = 0
        for row in rows:
            run_id, run_type, config_hash, fix_ver, start_ts, end_ts, status, man_hash = row
            existing = (
                self._session.query(DecisionRun).filter(DecisionRun.run_key == str(run_id)).first()
            )
            if existing:
                continue
            run = DecisionRun(
                decision_run_id=str(uuid4()),
                run_key=str(run_id),
                run_kind=_run_kind(str(run_type or "")),
                status=_RUN_STATUS_MAP.get(str(status or ""), RunStatus.COMPLETED),
                portfolio_book_id=self._default_book_id,
                decision_as_of=start_ts if start_ts else datetime.now(UTC),
                started_at=start_ts if start_ts else datetime.now(UTC),
                completed_at=end_ts,
                config_hash=str(config_hash or ""),
                strategy_version_id=self._default_strategy_version_id,
            )
            self._session.add(run)
            count += 1
        self._session.flush()
        logger.info("imported_decision_runs", count=count)
        return count

    def _import_audit_events(self) -> int:
        try:
            rows = self._ddb.execute(
                "SELECT event_id, event_type, timestamp, run_id, payload"
                " FROM events ORDER BY timestamp"
            ).fetchall()
        except duckdb.CatalogException:
            return 0

        count = 0
        for row in rows:
            event_id, event_type, ts, run_id, payload = row
            existing = (
                self._session.query(AuditEvent).filter(AuditEvent.event_id == str(event_id)).first()
            )
            if existing:
                continue
            ae = AuditEvent(
                event_id=str(event_id),
                decision_run_id=self._resolve_run_id(str(run_id)) if run_id else None,
                event_type=str(event_type),
                payload_json=json.dumps(payload) if not isinstance(payload, str) else str(payload),
                created_at=ts if ts else datetime.now(UTC),
            )
            self._session.add(ae)
            count += 1
        self._session.flush()
        logger.info("imported_audit_events", count=count)
        return count

    def _import_portfolio_marks(self) -> int:
        try:
            rows = self._ddb.execute(
                "SELECT equity_date, equity, cash, regime, book"
                " FROM equity_curve ORDER BY equity_date"
            ).fetchall()
        except duckdb.CatalogException:
            return 0

        count = 0
        for row in rows:
            eq_date, equity, cash, regime, book = row
            pm = PortfolioMark(
                mark_id=str(uuid4()),
                portfolio_book_id=self._default_book_id,
                effective_date=eq_date,
                cash=float(cash or 0.0),
                equity=float(equity or 0.0),
                gross_exposure=float(equity or 0.0),
                regime=str(regime or "UNKNOWN"),
                mark_as_of=datetime.combine(eq_date, datetime.min.time(), tzinfo=UTC)
                if eq_date
                else datetime.now(UTC),
            )
            self._session.add(pm)
            count += 1
        self._session.flush()
        logger.info("imported_portfolio_marks", count=count)
        return count

    def _import_positions(self) -> int:
        try:
            rows = self._ddb.execute(
                "SELECT symbol, quantity, avg_cost, current_price,"
                " market_value, unrealized_pl, stop_price"
                " FROM positions WHERE quantity > 0"
            ).fetchall()
        except duckdb.CatalogException:
            return 0

        count = 0
        for row in rows:
            symbol, quantity, avg_cost, current_price, market_value, unrealized_pl, stop_price = row
            sec_id = self._ensure_security(str(symbol))
            existing = (
                self._session.query(PositionCurrent)
                .filter(
                    PositionCurrent.book_id == self._default_book_id,
                    PositionCurrent.security_id == sec_id,
                )
                .first()
            )
            if existing:
                continue
            pc = PositionCurrent(
                book_id=self._default_book_id,
                security_id=sec_id,
                symbol=str(symbol),
                quantity=float(quantity or 0.0),
                avg_cost=float(avg_cost or 0.0),
                current_price=float(current_price or 0.0),
                market_value=float(market_value or 0.0),
                unrealized_pl=float(unrealized_pl or 0.0),
                stop_price=float(stop_price) if stop_price else None,
            )
            self._session.add(pc)
            count += 1
        self._session.flush()
        logger.info("imported_positions", count=count)
        return count

    def _import_orders(self) -> int:
        try:
            rows = self._ddb.execute(
                "SELECT order_id, symbol, action, quantity, order_type,"
                " limit_price, status, submitted_at, fill_date,"
                " filled_quantity, avg_fill_price FROM orders ORDER BY submitted_at"
            ).fetchall()
        except duckdb.CatalogException:
            return 0

        from alpha_quant.adapters.postgres.tables import OrderSide, OrderStatus

        side_map: dict[str, OrderSide] = {"buy": OrderSide.BUY, "sell": OrderSide.SELL}
        status_map: dict[str, OrderStatus] = {
            "pending": OrderStatus.PENDING,
            "submitted": OrderStatus.SUBMITTED,
            "filled": OrderStatus.FILLED,
            "cancelled": OrderStatus.CANCELLED,
        }

        count = 0
        for row in rows:
            (
                order_id,
                symbol,
                action,
                quantity,
                order_type,
                limit_price,
                status,
                submitted_at,
                fill_date,
                filled_quantity,
                avg_fill_price,
            ) = row
            existing = (
                self._session.query(PaperOrder).filter(PaperOrder.order_id == str(order_id)).first()
            )
            if existing:
                continue
            po = PaperOrder(
                order_id=str(order_id),
                portfolio_book_id=self._default_book_id,
                security_id=self._ensure_security(str(symbol)),
                symbol=str(symbol),
                side=side_map.get(str(action or "").lower(), OrderSide.BUY),
                quantity=float(quantity or 0.0),
                status=status_map.get(str(status or "").lower(), OrderStatus.PENDING),
                submitted_at=submitted_at if submitted_at else datetime.now(UTC),
                filled_quantity=float(filled_quantity) if filled_quantity else None,
                idempotency_key=f"imported:{order_id}",
            )
            self._session.add(po)
            count += 1
        self._session.flush()
        logger.info("imported_orders", count=count)
        return count

    def _import_fills(self) -> int:
        from alpha_quant.adapters.postgres.tables import FillQuality, OrderSide

        try:
            rows = self._ddb.execute(
                "SELECT fill_id, order_id, symbol, quantity, price, filled_at"
                " FROM fills ORDER BY filled_at"
            ).fetchall()
        except duckdb.CatalogException:
            return 0

        count = 0
        for row in rows:
            fill_id, order_id, symbol, quantity, price, filled_at = row
            existing = (
                self._session.query(PaperFill).filter(PaperFill.fill_id == str(fill_id)).first()
            )
            if existing:
                continue
            side = OrderSide.BUY if (quantity or 0) > 0 else OrderSide.SELL
            pf = PaperFill(
                fill_id=str(fill_id),
                order_id=str(order_id),
                security_id=self._ensure_security(str(symbol)),
                symbol=str(symbol),
                side=side,
                quantity=abs(float(quantity or 0.0)),
                price=float(price or 0.0),
                fill_key=str(fill_id),
                quality=FillQuality.OPEN,
                fee=0.0,
                booked_at=filled_at if filled_at else datetime.now(UTC),
            )
            self._session.add(pf)
            count += 1
        self._session.flush()
        logger.info("imported_fills", count=count)
        return count

    def _import_candidate_evaluations(self) -> int:
        try:
            rows = self._ddb.execute(
                "SELECT decision_id, run_id, symbol, decision_date,"
                " action, confidence, reasons, candidate_json"
                " FROM decisions ORDER BY decision_date"
            ).fetchall()
        except duckdb.CatalogException:
            return 0

        count = 0
        for row in rows:
            (
                decision_id,
                run_id,
                symbol,
                decision_date,
                action,
                confidence,
                reasons,
                candidate_json,
            ) = row
            run = (
                self._session.query(DecisionRun).filter(DecisionRun.run_key == str(run_id)).first()
            )
            if not run:
                continue
            sec_id = self._ensure_security(str(symbol))

            gate_results = {}
            block_reason: str | None = None
            if candidate_json:
                try:
                    cj = (
                        json.loads(candidate_json)
                        if isinstance(candidate_json, str)
                        else candidate_json
                    )
                    gate_results = cj.get("gate_results", {})
                    block_reason = cj.get("block_reason")
                except (json.JSONDecodeError, TypeError):  # fmt: skip
                    pass

            existing_ce = (
                self._session.query(CandidateEvaluation)
                .filter(
                    CandidateEvaluation.decision_run_id == run.decision_run_id,
                    CandidateEvaluation.symbol == str(symbol),
                )
                .first()
            )
            if existing_ce:
                continue

            ce = CandidateEvaluation(
                candidate_id=str(uuid4()),
                decision_run_id=run.decision_run_id,
                portfolio_book_id=self._default_book_id,
                security_id=sec_id,
                symbol=str(symbol),
                composite_score=float(confidence or 0.0),
                regime="",
                blocked=bool(block_reason),
                block_reason=block_reason,
                gate_results=json.dumps(gate_results),
            )
            self._session.add(ce)
            self._session.flush()

            if reasons:
                try:
                    reasons_list = json.loads(reasons) if isinstance(reasons, str) else reasons
                    if isinstance(reasons_list, list):
                        for _i, r in enumerate(reasons_list):  # noqa: B007
                            pe = PolicyEvaluation(
                                evaluation_id=str(uuid4()),
                                candidate_id=ce.candidate_id,
                                policy_name="reason",
                                policy_version="imported",
                                reason=str(r),
                                details_json="{}",
                            )
                            self._session.add(pe)
                except (json.JSONDecodeError, TypeError):  # fmt: skip
                    pass
            count += 1
        self._session.flush()
        logger.info("imported_candidate_evaluations", count=count)
        return count

    def _resolve_run_id(self, run_key: str) -> str | None:
        run = self._session.query(DecisionRun).filter(DecisionRun.run_key == run_key).first()
        return run.decision_run_id if run else None


def run_import(
    duckdb_path: str = "data/state.db",
    postgres_url: str = DEFAULT_DATABASE_URL,
) -> int:
    importer = LegacyDuckDBImporter(duckdb_path=duckdb_path, postgres_url=postgres_url)
    return importer.run()
