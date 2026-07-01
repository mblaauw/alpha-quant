# ruff: noqa: E501

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from alpha_quant.contracts.operational import (
    AuditEvent,
    CandidateEvaluation,
    Command,
    CommandEnvelope,
    CommandStatus,
    CorporateActionBooking,
    CurrentHalt,
    DecisionBatch,
    DecisionRun,
    FillBookingCommand,
    FillBookingResult,
    HaltCommand,
    HaltReason,
    OrderSide,
    PolicyEvaluation,
    PortfolioBook,
    PortfolioMark,
    PortfolioState,
    PositionCurrent,
    RiskEvent,
    RunKind,
    RunReservation,
    RunStatus,
    Strategy,
)
from alpha_quant.domain.advice import AdviceArtifact, OperatorOverride
from alpha_quant.domain.risk import RiskPolicy
from alpha_quant.domain.scorecard import (
    Recommendation,
    Scorecard,
    ScorecardComponent,
)


class PostgresOperationalStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Run lifecycle ---

    def reserve_run(self, request: RunReservation) -> DecisionRun:
        run_id = str(uuid4())
        now = datetime.now(UTC)
        self.session.execute(
            text(
                """
                INSERT INTO run.decision_run
                    (decision_run_id, run_key, run_kind, status,
                     strategy_version_id, portfolio_book_id,
                     decision_as_of, resolved_snapshot_id,
                     alpha_lake_api_version, alpha_lake_contract_version,
                     config_hash, request_hash, response_hash,
                     started_at)
                VALUES
                    (:rid, :rk, :kind, :status,
                     :svid, :pbid,
                     :dao, :sid,
                     :apiv, :ctv,
                     :ch, :reqh, :resh,
                     :now)
                """
            ),
            {
                "rid": run_id,
                "rk": request.run_key,
                "kind": request.run_kind.value,
                "status": RunStatus.RESERVED.value,
                "svid": str(request.strategy_version_id),
                "pbid": str(request.portfolio_book_id),
                "dao": request.decision_as_of,
                "sid": request.resolved_snapshot_id,
                "apiv": request.alpha_lake_api_version,
                "ctv": request.alpha_lake_contract_version,
                "ch": request.config_hash,
                "reqh": request.request_hash,
                "resh": request.response_hash,
                "now": now,
            },
        )
        return DecisionRun(
            decision_run_id=UUID(run_id),
            run_key=request.run_key,
            run_kind=request.run_kind,
            status=RunStatus.RESERVED,
            strategy_version_id=request.strategy_version_id,
            portfolio_book_id=request.portfolio_book_id,
            decision_as_of=request.decision_as_of,
            execution_as_of=None,
            resolved_snapshot_id=request.resolved_snapshot_id,
            alpha_lake_api_version=request.alpha_lake_api_version,
            alpha_lake_contract_version=request.alpha_lake_contract_version,
            config_hash=request.config_hash,
            request_hash=request.request_hash,
            response_hash=request.response_hash,
            started_at=now,
        )

    def start_run(self, run_id: UUID) -> None:
        self.session.execute(
            text("UPDATE run.decision_run SET status = :s WHERE decision_run_id = :rid"),
            {"s": RunStatus.RUNNING.value, "rid": str(run_id)},
        )

    def complete_run(self, run_id: UUID, status: str, failure_reason: str | None = None) -> None:
        self.session.execute(
            text(
                """
                UPDATE run.decision_run
                SET status = :s, completed_at = :now, failure_reason = :fr
                WHERE decision_run_id = :rid
                AND status IN ('RUNNING', 'HALTED')
                """
            ),
            {
                "s": status,
                "now": datetime.now(UTC),
                "fr": failure_reason,
                "rid": str(run_id),
            },
        )

    # --- Decision batch ---

    def commit_decision_batch(self, batch: DecisionBatch) -> None:
        for cand in batch.candidates:
            self.session.execute(
                text(
                    """
                    INSERT INTO run.candidate_evaluation
                        (candidate_id, decision_run_id, portfolio_book_id,
                         security_id, symbol, composite_score, regime,
                         blocked, block_reason, gate_results)
                    VALUES
                        (:cid, :rid, :pbid,
                         :sid, :sym, :cs, :reg,
                         :bl, :br, :gr)
                    """
                ),
                {
                    "cid": str(cand.candidate_id),
                    "rid": str(batch.decision_run_id),
                    "pbid": str(cand.portfolio_book_id),
                    "sid": str(cand.security_id),
                    "sym": cand.symbol,
                    "cs": str(cand.composite_score),
                    "reg": cand.regime,
                    "bl": cand.blocked,
                    "br": cand.block_reason,
                    "gr": cand.gate_results,
                },
            )
            for pe in batch.policy_evals:
                self.session.execute(
                    text(
                        """
                        INSERT INTO run.policy_evaluation
                            (evaluation_id, candidate_id, policy_name,
                             policy_version, score, passed, reason, details_json)
                        VALUES
                            (:eid, :cid, :pn,
                             :pv, :sc, :pa, :re, :dj)
                        """
                    ),
                    {
                        "eid": str(pe.evaluation_id),
                        "cid": str(pe.candidate_id),
                        "pn": pe.policy_name,
                        "pv": pe.policy_version,
                        "sc": str(pe.score) if pe.score is not None else None,
                        "pa": pe.passed,
                        "re": pe.reason,
                        "dj": pe.details_json,
                    },
                )

    # --- Fills ---

    def book_fill(self, command: FillBookingCommand) -> FillBookingResult:
        existing = self.session.execute(
            text("SELECT fill_id, fill_key FROM trade.paper_fill WHERE fill_key = :fk"),
            {"fk": command.fill_key},
        ).fetchone()

        if existing is not None:
            return FillBookingResult(
                fill_id=UUID(existing._mapping["fill_id"]),
                fill_key=existing._mapping["fill_key"],
                already_booked=True,
            )

        fill_id = str(uuid4())
        now = datetime.now(UTC)

        side_sign = -1 if command.side == OrderSide.BUY else 1
        cash_amount = side_sign * command.price * command.quantity - command.fee
        self.session.execute(
            text(
                """
                INSERT INTO trade.paper_fill
                    (fill_id, order_id, security_id, symbol, side,
                     quantity, price, fill_key, quality, fee, booked_at)
                VALUES
                    (:fid, :oid, :sid, :sym, :side,
                     :qty, :pr, :fk, :ql, :fee, :now)
                """
            ),
            {
                "fid": fill_id,
                "oid": str(command.order_id),
                "sid": str(command.security_id),
                "sym": command.symbol,
                "side": command.side.value,
                "qty": str(command.quantity),
                "pr": str(command.price),
                "fk": command.fill_key,
                "ql": command.quality.value,
                "fee": str(command.fee),
                "now": now,
            },
        )
        self.session.execute(
            text(
                """
                INSERT INTO trade.cash_ledger_entry
                    (entry_id, portfolio_book_id, fill_id, amount, currency, reason, booked_at)
                VALUES
                    (:eid, :pbid, :fid, :amt, :cur, :rea, :now)
                """
            ),
            {
                "eid": str(uuid4()),
                "pbid": str(command.portfolio_book_id),
                "fid": fill_id,
                "amt": str(cash_amount),
                "cur": "USD",
                "rea": command.reason,
                "now": now,
            },
        )
        return FillBookingResult(
            fill_id=UUID(fill_id),
            fill_key=command.fill_key,
            already_booked=False,
        )

    # --- Portfolio ---

    def load_portfolio(self, book_id: UUID) -> PortfolioState:
        cash_row = self.session.execute(
            text("SELECT cash FROM projection.portfolio_current WHERE book_id = :bid"),
            {"bid": str(book_id)},
        ).fetchone()

        cash = cash_row._mapping["cash"] if cash_row else Decimal("0")

        pos_rows = self.session.execute(
            text(
                """
                SELECT security_id, symbol, quantity, avg_cost, current_price,
                       market_value, unrealized_pl, stop_price
                FROM projection.position_current
                WHERE book_id = :bid AND quantity != 0
                """
            ),
            {"bid": str(book_id)},
        ).fetchall()

        positions = [
            PositionCurrent(
                book_id=book_id,
                security_id=UUID(row._mapping["security_id"]),
                symbol=row._mapping["symbol"],
                quantity=row._mapping["quantity"],
                avg_cost=row._mapping["avg_cost"],
                current_price=row._mapping.get("current_price"),
                market_value=row._mapping.get("market_value"),
                unrealized_pl=row._mapping.get("unrealized_pl"),
                stop_price=row._mapping.get("stop_price"),
            )
            for row in pos_rows
        ]

        return PortfolioState(book_id=book_id, cash=cash, positions=positions, open_orders=[])

    def save_portfolio_mark(self, mark: PortfolioMark) -> None:
        self.session.execute(
            text(
                """
                INSERT INTO trade.portfolio_mark
                    (mark_id, portfolio_book_id, effective_date, cash, equity,
                     gross_exposure, regime, mark_as_of)
                VALUES
                    (:mid, :pbid, :ed, :c, :eq,
                     :ge, :reg, :mao)
                ON CONFLICT (portfolio_book_id, effective_date) DO UPDATE SET
                    cash = :c2,
                    equity = :eq2,
                    gross_exposure = :ge2,
                    regime = :reg2,
                    mark_as_of = :mao2
                """
            ),
            {
                "mid": str(mark.mark_id),
                "pbid": str(mark.portfolio_book_id),
                "ed": mark.effective_date,
                "c": str(mark.cash),
                "eq": str(mark.equity),
                "ge": str(mark.gross_exposure),
                "reg": mark.regime,
                "mao": mark.mark_as_of,
                "c2": str(mark.cash),
                "eq2": str(mark.equity),
                "ge2": str(mark.gross_exposure),
                "reg2": mark.regime,
                "mao2": mark.mark_as_of,
            },
        )

    # --- Halts ---

    def set_halt(self, command: HaltCommand) -> None:
        self.session.execute(
            text(
                """
                INSERT INTO audit.halt_transition
                    (halt_id, portfolio_book_id, reason, details, halted_at)
                VALUES
                    (:hid, :pbid, :rea, :det, :now)
                """
            ),
            {
                "hid": str(uuid4()),
                "pbid": str(command.portfolio_book_id),
                "rea": command.reason.value,
                "det": command.details,
                "now": datetime.now(UTC),
            },
        )
        self.session.execute(
            text(
                """
                INSERT INTO ops.current_halt
                    (book_id, halted, reason, details, halted_at)
                VALUES (:bid, TRUE, :rea, :det, :now)
                ON CONFLICT (book_id) DO UPDATE SET
                    halted = TRUE,
                    reason = :rea,
                    details = :det,
                    halted_at = :now
                """
            ),
            {
                "bid": str(command.portfolio_book_id),
                "rea": command.reason.value,
                "det": command.details,
                "now": datetime.now(UTC),
            },
        )

    def clear_halt(self, book_id: UUID) -> None:
        row = self.session.execute(
            text("SELECT reason, details, halted_at FROM ops.current_halt WHERE book_id = :bid"),
            {"bid": str(book_id)},
        ).fetchone()
        self.session.execute(
            text("UPDATE ops.current_halt SET halted = FALSE WHERE book_id = :bid"),
            {"bid": str(book_id)},
        )
        if row:
            self.session.execute(
                text("""
                    UPDATE audit.halt_transition
                    SET resumed_at = NOW()
                    WHERE portfolio_book_id = :bid AND resumed_at IS NULL
                """),
                {"bid": str(book_id)},
            )

    def current_halt(self, book_id: UUID) -> CurrentHalt | None:
        row = self.session.execute(
            text(
                "SELECT halted, reason, details, halted_at"
                " FROM ops.current_halt WHERE book_id = :bid"
            ),
            {"bid": str(book_id)},
        ).fetchone()

        if row is None:
            return None
        return CurrentHalt(
            book_id=book_id,
            halted=row._mapping["halted"],
            reason=HaltReason(row._mapping["reason"]) if row._mapping["reason"] else None,
            details=row._mapping["details"],
            halted_at=row._mapping["halted_at"],
        )

    # --- Projections ---

    def rebuild_projections(self, book_id: UUID) -> None:
        self.session.execute(
            text("DELETE FROM projection.position_current WHERE book_id = :bid"),
            {"bid": str(book_id)},
        )
        self.session.execute(
            text("DELETE FROM projection.portfolio_current WHERE book_id = :bid"),
            {"bid": str(book_id)},
        )
        # Rebuild positions: compute quantity, avg_cost, and use latest fill price
        # as current_price, then derive market_value and unrealized_pl.
        self.session.execute(
            text(
                """
                INSERT INTO projection.position_current
                    (book_id, security_id, symbol, quantity, avg_cost,
                     current_price, market_value, unrealized_pl)
                WITH position_agg AS (
                    SELECT
                        po.portfolio_book_id,
                        pf.security_id,
                        pf.symbol,
                        SUM(CASE WHEN pf.side = 'buy' THEN pf.quantity ELSE -pf.quantity END) AS net_qty,
                        CASE
                            WHEN SUM(CASE WHEN pf.side = 'buy' THEN pf.quantity ELSE 0 END) > 0
                            THEN SUM(
                                pf.price * pf.quantity * CASE WHEN pf.side = 'buy' THEN 1 ELSE -1 END
                            ) / SUM(CASE WHEN pf.side = 'buy' THEN pf.quantity ELSE 0 END)
                            ELSE 0
                        END AS avg_cost
                    FROM trade.paper_fill pf
                    JOIN trade.paper_order po ON pf.order_id = po.order_id
                    WHERE po.portfolio_book_id = :bid
                    GROUP BY po.portfolio_book_id, pf.security_id, pf.symbol
                    HAVING SUM(CASE WHEN pf.side = 'buy' THEN pf.quantity ELSE -pf.quantity END) != 0
                ),
                latest_price AS (
                    SELECT DISTINCT ON (pf.security_id)
                        pf.security_id,
                        pf.price AS last_price
                    FROM trade.paper_fill pf
                    JOIN trade.paper_order po ON pf.order_id = po.order_id
                    WHERE po.portfolio_book_id = :bid2
                    ORDER BY pf.security_id, pf.booked_at DESC
                )
                SELECT
                    pa.portfolio_book_id,
                    pa.security_id,
                    pa.symbol,
                    pa.net_qty,
                    pa.avg_cost,
                    COALESCE(lp.last_price, 0) AS current_price,
                    CAST(pa.net_qty * COALESCE(lp.last_price, 0) AS NUMERIC(28,10)) AS market_value,
                    CAST(
                        (COALESCE(lp.last_price, 0) - pa.avg_cost)
                        * CASE WHEN pa.net_qty > 0 THEN pa.net_qty ELSE 0 END
                    AS NUMERIC(28,10)) AS unrealized_pl
                FROM position_agg pa
                LEFT JOIN latest_price lp ON pa.security_id = lp.security_id
                """
            ),
            {"bid": str(book_id), "bid2": str(book_id)},
        )
        # Rebuild portfolio: compute cash from ledger, equity/gross_exposure from positions.
        # Row was already deleted above, so plain INSERT (no ON CONFLICT needed).
        self.session.execute(
            text(
                """
                INSERT INTO projection.portfolio_current
                    (book_id, cash, equity, gross_exposure, regime, updated_at)
                WITH cash_agg AS (
                    SELECT COALESCE(SUM(amount), 0) AS total_cash
                    FROM trade.cash_ledger_entry
                    WHERE portfolio_book_id = :bid
                ),
                pos_agg AS (
                    SELECT
                        COALESCE(SUM(market_value), 0) AS total_mv,
                        COALESCE(SUM(ABS(market_value)), 0) AS total_exposure
                    FROM projection.position_current
                    WHERE book_id = :bid2
                ),
                last_regime AS (
                    SELECT regime FROM trade.portfolio_mark
                    WHERE portfolio_book_id = :bid3
                    ORDER BY mark_as_of DESC LIMIT 1
                )
                SELECT
                    :bid4,
                    c.total_cash,
                    c.total_cash + p.total_mv AS equity,
                    p.total_exposure,
                    COALESCE(lr.regime, 'unknown'),
                    :now
                FROM cash_agg c, pos_agg p
                LEFT JOIN last_regime lr ON TRUE
                """
            ),
            {
                "bid": str(book_id),
                "bid2": str(book_id),
                "bid3": str(book_id),
                "bid4": str(book_id),
                "now": datetime.now(UTC),
            },
        )

    # --- Scorecards ---

    def save_scorecard(self, scorecard: Scorecard, decision_run_id: str) -> str:
        if not scorecard.security_id:
            raise ValueError("security_id is required on scorecard")
        if not scorecard.facts_hash:
            raise ValueError("facts_hash is required on scorecard")
        if not scorecard.config_hash:
            raise ValueError("config_hash is required on scorecard")
        if not scorecard.strategy_version:
            raise ValueError("strategy_version is required on scorecard")

        now = datetime.now(UTC)
        scorecard_id = str(uuid4())

        self.session.execute(
            text("""
                INSERT INTO run.scorecard
                    (scorecard_id, decision_run_id, portfolio_book_id,
                     symbol, security_id, as_of, snapshot_id,
                     facts_hash, config_hash, strategy_version,
                     recommendation, confidence, total_score, data_quality, created_at)
                VALUES
                    (:sid, :rid, :pbid,
                     :sym, :secid, :ao, :snap,
                     :fh, :ch, :sv,
                     :rec, :conf, :ts, :dq, :now)
            """),
            {
                "sid": scorecard_id,
                "rid": decision_run_id,
                "pbid": scorecard.portfolio_book_id or "",
                "sym": scorecard.symbol,
                "secid": scorecard.security_id,
                "ao": scorecard.as_of or now,
                "snap": scorecard.snapshot_id,
                "fh": scorecard.facts_hash,
                "ch": scorecard.config_hash,
                "sv": scorecard.strategy_version,
                "rec": scorecard.recommendation.value
                if scorecard.recommendation
                else Recommendation.do_nothing.value,
                "conf": str(scorecard.confidence),
                "ts": str(scorecard.total_score),
                "dq": scorecard.data_quality.value if scorecard.data_quality else "pass",
                "now": now,
            },
        )

        for comp in scorecard.components:
            self.session.execute(
                text("""
                    INSERT INTO run.scorecard_component
                        (component_id, scorecard_id, name, category,
                         score, state, weight, passed, reason, details_json)
                    VALUES
                        (:cid, :sid, :n, :cat,
                         :sc, :st, :w, :p, :r, :dj)
                """),
                {
                    "cid": str(uuid4()),
                    "sid": scorecard_id,
                    "n": comp.name,
                    "cat": comp.category,
                    "sc": str(comp.score),
                    "st": comp.state.value if comp.state else "pass",
                    "w": str(comp.weight),
                    "p": comp.passed,
                    "r": comp.reason,
                    "dj": comp.details_json or "{}",
                },
            )

        return scorecard_id

    def load_scorecard(self, scorecard_id: str) -> Scorecard | None:
        row = self.session.execute(
            text("""
                SELECT scorecard_id, decision_run_id, portfolio_book_id,
                       symbol, security_id, as_of, snapshot_id,
                       facts_hash, config_hash, strategy_version,
                       recommendation, confidence, total_score, data_quality, created_at
                FROM run.scorecard WHERE scorecard_id = :sid
            """),
            {"sid": scorecard_id},
        ).fetchone()
        if row is None:
            return None
        return PostgresOperationalStore._row_to_scorecard(row, self.session)

    def load_scorecards_for_run(self, run_id: str) -> list[Scorecard]:
        rows = self.session.execute(
            text("""
                SELECT scorecard_id, decision_run_id, portfolio_book_id,
                       symbol, security_id, as_of, snapshot_id,
                       facts_hash, config_hash, strategy_version,
                       recommendation, confidence, total_score, data_quality, created_at
                FROM run.scorecard WHERE decision_run_id = :rid
                ORDER BY total_score DESC
            """),
            {"rid": run_id},
        ).fetchall()
        return [PostgresOperationalStore._row_to_scorecard(r, self.session) for r in rows]

    # --- Advice ---

    def save_advice_artifact(self, advice: AdviceArtifact) -> str:
        import json

        now = datetime.now(UTC)
        advice_id = str(uuid4())
        rec = advice.recommendation

        self.session.execute(
            text("""
                INSERT INTO run.advice_artifact
                    (advice_id, scorecard_id,
                     scope, scope_id, snapshot_id, input_fingerprint,
                     llm_provider, llm_model, prompt_version,
                     input_hash, output_hash, validation_status,
                     recommendation, headline, summary,
                     rationale_json, risks_json,
                     confidence_label, what_changed_json, override_guidance_json,
                     interpretation, key_evidence_json, key_caveats_json,
                     data_quality_notes, decision_context,
                     educational_context, what_could_change_json,
                     deterministic_differs, stale, created_at)
                VALUES
                    (:aid, :sid,
                     :sc, :scid, :snap, :fp,
                     :lp, :lm, :pv,
                     :ih, :oh, :vs,
                     :rec, :hl, :sum,
                     :rj, :rkj,
                     :cl, :wcj, :ogj,
                     :int, :kej, :kcj,
                     :dqn, :dc,
                     :ec, :wccj,
                     :dd, :st, :now)
            """),
            {
                "aid": advice_id,
                "sid": advice.scorecard_id,
                "sc": advice.scope,
                "scid": advice.scope_id,
                "snap": advice.snapshot_id or None,
                "fp": advice.input_fingerprint or None,
                "lp": advice.llm_provider,
                "lm": advice.llm_model,
                "pv": advice.prompt_version,
                "ih": advice.input_hash,
                "oh": advice.output_hash,
                "vs": advice.validation_status,
                "rec": rec.recommendation.value if rec else Recommendation.do_nothing.value,
                "hl": rec.headline if rec else "",
                "sum": rec.summary if rec else "",
                "rj": json.dumps(rec.key_reasons if rec else []),
                "rkj": json.dumps(rec.main_risks if rec else []),
                "cl": rec.confidence_label if rec else "medium",
                "wcj": json.dumps(rec.what_changed if rec else []),
                "ogj": json.dumps(rec.override_guidance if rec else []),
                "int": rec.interpretation if rec else "",
                "kej": json.dumps(rec.key_evidence if rec else []),
                "kcj": json.dumps(rec.key_caveats if rec else []),
                "dqn": rec.data_quality_notes if rec else "",
                "dc": rec.decision_context if rec else "",
                "ec": rec.educational_context if rec else "",
                "wccj": json.dumps(rec.what_could_change if rec else []),
                "dd": advice.deterministic_differs,
                "st": advice.stale,
                "now": now,
            },
        )
        return advice_id

    def mark_explanations_stale(
        self, scope: str = "", scope_id: str = "", scorecard_id: str = ""
    ) -> int:
        import structlog

        logger = structlog.get_logger()

        where = []
        params: dict[str, object] = {}
        if scope:
            where.append("scope = :sc")
            params["sc"] = scope
        if scope_id:
            where.append("scope_id = :scid")
            params["scid"] = scope_id
        if scorecard_id:
            where.append("scorecard_id = :scidref")
            params["scidref"] = scorecard_id
        where_clause = " AND ".join(where) if where else "TRUE"

        sql = f"UPDATE run.advice_artifact SET stale = TRUE WHERE {where_clause}"
        result = self.session.execute(text(sql), params)
        count = result.rowcount
        logger.info(
            "explanations_marked_stale",
            scope=scope,
            scope_id=scope_id,
            scorecard_id=scorecard_id,
            count=count,
        )
        return count

    def load_advice_artifacts(self, scope: str = "", scope_id: str = "") -> list[AdviceArtifact]:
        from alpha_quant.domain.advice import AdviceRecommendation

        where = []
        params: dict[str, object] = {}
        if scope:
            where.append("scope = :sc")
            params["sc"] = scope
        if scope_id:
            where.append("scope_id = :scid")
            params["scid"] = scope_id
        where_clause = " AND ".join(where) if where else "TRUE"

        rows = self.session.execute(
            text(f"""
                SELECT advice_id, scorecard_id, scope, scope_id,
                       snapshot_id, input_fingerprint,
                       validation_status, stale,
                       recommendation, headline, summary,
                       rationale_json AS key_reasons,
                       risks_json AS main_risks,
                       confidence_label, what_changed_json, override_guidance_json,
                       interpretation, key_evidence_json, key_caveats_json,
                       data_quality_notes, decision_context,
                       educational_context, what_could_change_json,
                       created_at
                FROM run.advice_artifact
                WHERE {where_clause}
                ORDER BY created_at DESC
            """),
            params,
        ).fetchall()

        def _load_json(val: str | None, default: str = "[]") -> list:
            try:
                if isinstance(val, str):
                    result = json.loads(val) if val else json.loads(default)
                elif val is None:
                    result = json.loads(default)
                else:
                    result = val
            except (json.JSONDecodeError, TypeError):  # fmt: skip
                return json.loads(default)

            if isinstance(result, dict):
                items = []
                for v in result.values():
                    if isinstance(v, list):
                        items.extend(str(i) for i in v)
                    elif isinstance(v, str):
                        items.append(v)
                return items

            if isinstance(result, list):
                return [str(i) for i in result]

            return json.loads(default)

        return [
            AdviceArtifact(
                advice_id=str(r._mapping["advice_id"]),
                scorecard_id=str(r._mapping["scorecard_id"]),
                scope=str(r._mapping.get("scope", "")),
                scope_id=str(r._mapping.get("scope_id", "")),
                snapshot_id=str(r._mapping.get("snapshot_id") or ""),
                input_fingerprint=str(r._mapping.get("input_fingerprint") or ""),
                validation_status=str(r._mapping.get("validation_status", "")),
                stale=bool(r._mapping.get("stale", False)),
                recommendation=AdviceRecommendation(
                    recommendation=r._mapping.get(
                        "recommendation", Recommendation.do_nothing.value
                    ),
                    confidence_label=str(r._mapping.get("confidence_label", "medium")),
                    headline=str(r._mapping.get("headline", "")),
                    summary=str(r._mapping.get("summary", "")),
                    interpretation=str(r._mapping.get("interpretation", "")),
                    educational_context=str(r._mapping.get("educational_context", "")),
                    key_reasons=_load_json(r._mapping.get("key_reasons")),
                    key_evidence=_load_json(r._mapping.get("key_evidence_json")),
                    key_caveats=_load_json(r._mapping.get("key_caveats_json")),
                    main_risks=_load_json(r._mapping.get("main_risks")),
                    data_quality_notes=str(r._mapping.get("data_quality_notes", "")),
                    decision_context=str(r._mapping.get("decision_context", "")),
                    what_changed=_load_json(r._mapping.get("what_changed_json")),
                    what_could_change=_load_json(r._mapping.get("what_could_change_json")),
                    override_guidance=_load_json(r._mapping.get("override_guidance_json")),
                ),
                created_at=r._mapping.get("created_at"),
            )
            for r in rows
        ]

    # --- Operator Overrides ---

    def save_operator_override(self, override: OperatorOverride) -> str:
        now = datetime.now(UTC)
        override_id = str(uuid4())

        self.session.execute(
            text("""
                INSERT INTO audit.operator_override
                    (override_id, scorecard_id, command_id, actor_id,
                     original_recommendation, original_confidence,
                     override_action, modified_recommendation, reason, created_at)
                VALUES
                    (:oid, :sid, :cid, :aid,
                     :or, :oc,
                     :oa, :mr, :rea, :now)
            """),
            {
                "oid": override_id,
                "sid": override.scorecard_id,
                "cid": override.command_id,
                "aid": override.actor_id,
                "or": override.original_recommendation.value,
                "oc": str(override.original_confidence),
                "oa": override.override_action.value,
                "mr": override.modified_recommendation.value
                if override.modified_recommendation
                else None,
                "rea": override.reason,
                "now": now,
            },
        )
        return override_id

    # --- Risk Methods ---

    def list_risk_methods(self) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text("""
                SELECT risk_method_id, name, description, method_type,
                       default_params_json, is_active
                FROM core.risk_method ORDER BY name
            """),
        ).fetchall()
        return [
            {
                "risk_method_id": r._mapping["risk_method_id"],
                "name": r._mapping["name"],
                "description": r._mapping["description"],
                "method_type": r._mapping["method_type"],
                "default_params_json": r._mapping["default_params_json"],
                "is_active": r._mapping["is_active"],
            }
            for r in rows
        ]

    def set_book_risk_profile(self, book_id: UUID, risk_method_id: str, params_json: str) -> None:
        self.session.execute(
            text("""
                INSERT INTO core.book_risk_profile
                    (book_id, risk_method_id, params_json, updated_at)
                VALUES (:bid, :rmid, :pj, :now)
                ON CONFLICT (book_id) DO UPDATE SET
                    risk_method_id = :rmid2, params_json = :pj2, updated_at = :now
            """),
            {
                "bid": str(book_id),
                "rmid": risk_method_id,
                "rmid2": risk_method_id,
                "pj": params_json,
                "pj2": params_json,
                "now": datetime.now(UTC),
            },
        )

    def update_position_risk(
        self,
        book_id: UUID,
        security_id: str,
        stop_price: float | None = None,
        trail_price: float | None = None,
        risk_method_id: str | None = None,
        auto_trail_enabled: bool | None = None,
    ) -> None:
        self.session.execute(
            text("""
                INSERT INTO projection.position_risk_current
                    (book_id, security_id, stop_price, trail_price,
                     risk_method_id, auto_trail_enabled, last_adjusted_at)
                VALUES (:bid, :sid, :sp, :tp, :rmid, :ate, :now)
                ON CONFLICT (book_id, security_id) DO UPDATE SET
                    stop_price = COALESCE(:sp2, position_risk_current.stop_price),
                    trail_price = COALESCE(:tp2, position_risk_current.trail_price),
                    risk_method_id = COALESCE(:rmid2, position_risk_current.risk_method_id),
                    auto_trail_enabled = COALESCE(:ate2, position_risk_current.auto_trail_enabled),
                    last_adjusted_at = :now2
            """),
            {
                "bid": str(book_id),
                "sid": security_id,
                "sp": str(stop_price) if stop_price is not None else None,
                "tp": str(trail_price) if trail_price is not None else None,
                "rmid": risk_method_id,
                "ate": auto_trail_enabled if auto_trail_enabled is not None else True,
                "now": datetime.now(UTC),
                "sp2": str(stop_price) if stop_price is not None else None,
                "tp2": str(trail_price) if trail_price is not None else None,
                "rmid2": risk_method_id,
                "ate2": auto_trail_enabled,
                "now2": datetime.now(UTC),
            },
        )

    # --- Queries ---

    def list_strategies(self) -> list[Strategy]:
        rows = self.session.execute(
            text("SELECT strategy_id, name, created_at FROM core.strategy ORDER BY name")
        ).fetchall()
        return [
            Strategy(
                strategy_id=UUID(r._mapping["strategy_id"]),
                name=r._mapping["name"],
                created_at=r._mapping["created_at"],
            )
            for r in rows
        ]

    def list_books(self) -> list[PortfolioBook]:
        rows = self.session.execute(
            text("SELECT book_id, name, kind, created_at FROM core.portfolio_book ORDER BY name")
        ).fetchall()
        return [
            PortfolioBook(
                book_id=UUID(r._mapping["book_id"]),
                name=r._mapping["name"],
                kind=r._mapping["kind"],
                created_at=r._mapping["created_at"],
            )
            for r in rows
        ]

    def list_decision_runs(self, book_id: UUID, limit: int = 20) -> list[DecisionRun]:
        rows = self.session.execute(
            text(
                """
                SELECT decision_run_id, run_key, run_kind, status,
                       strategy_version_id, portfolio_book_id,
                       decision_as_of, execution_as_of,
                       resolved_snapshot_id,
                       alpha_lake_api_version, alpha_lake_contract_version,
                       config_hash, request_hash, response_hash,
                       started_at, completed_at, failure_reason
                FROM run.decision_run
                WHERE portfolio_book_id = :bid
                ORDER BY started_at DESC
                LIMIT :lim
                """
            ),
            {"bid": str(book_id), "lim": limit},
        ).fetchall()
        return [self._row_to_decision_run(r) for r in rows]

    def get_run_by_key(self, run_key: str) -> DecisionRun | None:
        row = self.session.execute(
            text(
                """
                SELECT decision_run_id, run_key, run_kind, status,
                       strategy_version_id, portfolio_book_id,
                       decision_as_of, execution_as_of,
                       resolved_snapshot_id,
                       alpha_lake_api_version, alpha_lake_contract_version,
                       config_hash, request_hash, response_hash,
                       started_at, completed_at, failure_reason
                FROM run.decision_run
                WHERE run_key = :rk
                """
            ),
            {"rk": run_key},
        ).fetchone()
        if row is None:
            return None
        return self._row_to_decision_run(row)

    def list_candidates(self, run_id: UUID, limit: int = 100) -> list[CandidateEvaluation]:
        rows = self.session.execute(
            text(
                """
                SELECT candidate_id, decision_run_id, portfolio_book_id,
                       security_id, symbol, composite_score, regime,
                       blocked, block_reason, gate_results
                FROM run.candidate_evaluation
                WHERE decision_run_id = :rid
                ORDER BY composite_score DESC
                LIMIT :lim
                """
            ),
            {"rid": str(run_id), "lim": limit},
        ).fetchall()
        return [
            CandidateEvaluation(
                candidate_id=UUID(r._mapping["candidate_id"]),
                decision_run_id=UUID(r._mapping["decision_run_id"]),
                portfolio_book_id=UUID(r._mapping["portfolio_book_id"]),
                security_id=UUID(r._mapping["security_id"]),
                symbol=r._mapping["symbol"],
                composite_score=r._mapping["composite_score"],
                regime=r._mapping["regime"],
                blocked=r._mapping["blocked"],
                block_reason=r._mapping["block_reason"],
                gate_results=r._mapping["gate_results"],
            )
            for r in rows
        ]

    def list_policy_evals(self, run_id: UUID, limit: int = 500) -> list[PolicyEvaluation]:
        rows = self.session.execute(
            text(
                """
                SELECT pe.evaluation_id, pe.candidate_id,
                       pe.policy_name, pe.policy_version,
                       pe.score, pe.passed, pe.reason, pe.details_json
                FROM run.policy_evaluation pe
                JOIN run.candidate_evaluation ce ON pe.candidate_id = ce.candidate_id
                WHERE ce.decision_run_id = :rid
                ORDER BY pe.policy_name
                LIMIT :lim
                """
            ),
            {"rid": str(run_id), "lim": limit},
        ).fetchall()
        return [
            PolicyEvaluation(
                evaluation_id=UUID(r._mapping["evaluation_id"]),
                candidate_id=UUID(r._mapping["candidate_id"]),
                policy_name=r._mapping["policy_name"],
                policy_version=r._mapping["policy_version"],
                score=r._mapping["score"],
                passed=r._mapping["passed"],
                reason=r._mapping["reason"],
                details_json=r._mapping["details_json"],
            )
            for r in rows
        ]

    def list_audit_events(self, run_id: UUID, limit: int = 200) -> list[AuditEvent]:
        rows = self.session.execute(
            text(
                """
                SELECT event_id, decision_run_id, event_type, payload_json, created_at
                FROM audit.audit_event
                WHERE decision_run_id = :rid
                ORDER BY created_at
                LIMIT :lim
                """
            ),
            {"rid": str(run_id), "lim": limit},
        ).fetchall()
        return [
            AuditEvent(
                event_id=UUID(r._mapping["event_id"]),
                decision_run_id=UUID(r._mapping["decision_run_id"]),
                event_type=r._mapping["event_type"],
                payload_json=r._mapping["payload_json"],
                created_at=r._mapping["created_at"],
            )
            for r in rows
        ]

    def list_positions(self, book_id: UUID) -> list[PositionCurrent]:
        rows = self.session.execute(
            text(
                """
                SELECT book_id, security_id, symbol, quantity, avg_cost,
                       current_price, market_value, unrealized_pl, stop_price
                FROM projection.position_current
                WHERE book_id = :bid AND quantity != 0
                """
            ),
            {"bid": str(book_id)},
        ).fetchall()
        return [
            PositionCurrent(
                book_id=book_id,
                security_id=UUID(r._mapping["security_id"]),
                symbol=r._mapping["symbol"],
                quantity=r._mapping["quantity"],
                avg_cost=r._mapping["avg_cost"],
                current_price=r._mapping.get("current_price"),
                market_value=r._mapping.get("market_value"),
                unrealized_pl=r._mapping.get("unrealized_pl"),
                stop_price=r._mapping.get("stop_price"),
            )
            for r in rows
        ]

    # --- Risk Policy ---

    def load_risk_policy(self, version_label: str = "default") -> RiskPolicy | None:
        row = self.session.execute(
            text("SELECT policy_json FROM core.risk_policy_version WHERE version_label = :vl"),
            {"vl": version_label},
        ).fetchone()
        if row is None:
            return None
        import json

        return RiskPolicy.model_validate(json.loads(row._mapping["policy_json"]))

    def save_risk_policy_version(self, policy: RiskPolicy) -> None:
        import json

        self.session.execute(
            text(
                "INSERT INTO core.risk_policy_version "
                "(version_label, policy_json, config_hash, created_at) "
                "VALUES (:vl, :pj, :ch, NOW()) "
                "ON CONFLICT (version_label) DO UPDATE SET "
                "policy_json = EXCLUDED.policy_json, "
                "config_hash = EXCLUDED.config_hash, "
                "created_at = NOW()"
            ),
            {
                "vl": policy.version_label,
                "pj": json.dumps(policy.model_dump(mode="json")),
                "ch": policy.config_hash(),
            },
        )

    def write_risk_event(self, event: RiskEvent) -> None:
        self.session.execute(
            text(
                "INSERT INTO audit.risk_event "
                "(risk_event_id, decision_run_id, event_type, severity, details_json, created_at) "
                "VALUES (:eid, :rid, :etype, :sev, :details, :now)"
            ),
            {
                "eid": str(event.risk_event_id),
                "rid": str(event.decision_run_id),
                "etype": event.event_type,
                "sev": event.severity,
                "details": event.details_json,
                "now": event.created_at,
            },
        )

    def write_corporate_action_booking(self, booking: CorporateActionBooking) -> None:
        self.session.execute(
            text(
                "INSERT INTO trade.corporate_action_booking "
                "(booking_id, portfolio_book_id, security_id, action_type, effective_date, ratio, amount) "
                "VALUES (:bid, :pbid, :sid, :at, :ed, :ratio, :amt)"
            ),
            {
                "bid": str(booking.booking_id),
                "pbid": str(booking.portfolio_book_id),
                "sid": str(booking.security_id),
                "at": booking.action_type,
                "ed": booking.effective_date,
                "ratio": booking.ratio,
                "amt": booking.amount,
            },
        )

    def write_run_lock_audit(self, run_key: str, action: str) -> None:
        self.session.execute(
            text(
                "INSERT INTO ops.run_lock_audit (lock_id, run_key, action, created_at) "
                "VALUES (:lid, :rk, :act, NOW())"
            ),
            {"lid": str(uuid4()), "rk": run_key, "act": action},
        )

    # --- Commands ---

    def submit_command(self, envelope: CommandEnvelope) -> Command:
        now = datetime.now(UTC)
        cmd = Command(
            command_id=uuid4(),
            type=envelope.type,
            idempotency_key=envelope.idempotency_key,
            status=CommandStatus.REQUESTED,
            actor_id=envelope.actor_id,
            actor_display_name=envelope.actor_display_name,
            book_id=envelope.book_id,
            reason=envelope.reason,
            expected_version=envelope.expected_version,
            payload_json=envelope.payload_json,
            requested_at=now,
        )
        self.session.execute(
            text("""
                INSERT INTO ops.command
                    (command_id, type, idempotency_key, status,
                     actor_id, actor_display_name, book_id, reason,
                     expected_version, payload_json, requested_at)
                VALUES
                    (:cid, :type, :ik, :s,
                     :aid, :adn, :bid, :rea,
                     :ev, :pj, :now)
            """),
            {
                "cid": str(cmd.command_id),
                "type": cmd.type,
                "ik": cmd.idempotency_key,
                "s": cmd.status.value,
                "aid": cmd.actor_id,
                "adn": cmd.actor_display_name,
                "bid": str(cmd.book_id) if cmd.book_id else None,
                "rea": cmd.reason,
                "ev": cmd.expected_version,
                "pj": cmd.payload_json,
                "now": now,
            },
        )
        self.session.execute(
            text("""
                INSERT INTO audit.audit_event
                    (event_id, decision_run_id, event_type, payload_json, created_at)
                VALUES (:eid, :rid, :et, :pj, :now)
            """),
            {
                "eid": str(uuid4()),
                "rid": None,
                "et": f"command.{cmd.type}.requested",
                "pj": f'{{"command_id":"{cmd.command_id}","type":"{cmd.type}","actor":"{cmd.actor_id}"}}',  # noqa: E501
                "now": now,
            },
        )
        return cmd

    def claim_command(self) -> Command | None:
        row = self.session.execute(
            text("""
                UPDATE ops.command SET status = :running, started_at = :now
                WHERE command_id = (
                    SELECT command_id FROM ops.command
                    WHERE status = :queued
                    ORDER BY requested_at ASC
                    LIMIT 1 FOR UPDATE SKIP LOCKED
                )
                RETURNING command_id, type, idempotency_key, status,
                    actor_id, actor_display_name, book_id, reason,
                    expected_version, payload_json, requested_at
            """),
            {
                "queued": CommandStatus.QUEUED.value,
                "running": CommandStatus.RUNNING.value,
                "now": datetime.now(UTC),
            },
        ).fetchone()
        if row is None:
            return None
        return self._row_to_command(row)

    def complete_command(
        self,
        command_id: UUID,
        status: CommandStatus,
        result: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            text("""
                UPDATE ops.command
                SET status = :s, finished_at = :now,
                    result_reference = :rr, failure_code = :fc, failure_message = :fm
                WHERE command_id = :cid
            """),
            {
                "cid": str(command_id),
                "s": status.value,
                "now": now,
                "rr": result,
                "fc": failure_code,
                "fm": failure_message,
            },
        )

    def get_command(self, command_id: UUID) -> Command | None:
        row = self.session.execute(
            text("""
                SELECT command_id, type, idempotency_key, status,
                    actor_id, actor_display_name, book_id, reason,
                    expected_version, payload_json, result_reference,
                    failure_code, failure_message, requested_at,
                    started_at, finished_at
                FROM ops.command WHERE command_id = :cid
            """),
            {"cid": str(command_id)},
        ).fetchone()
        if row is None:
            return None
        return self._row_to_command(row)

    def list_commands(self, book_id: UUID | None = None, limit: int = 50) -> list[Command]:
        if book_id:
            rows = self.session.execute(
                text("""
                    SELECT command_id, type, idempotency_key, status,
                        actor_id, actor_display_name, book_id, reason,
                        expected_version, payload_json, result_reference,
                        failure_code, failure_message, requested_at,
                        started_at, finished_at
                    FROM ops.command WHERE book_id = :bid
                    ORDER BY requested_at DESC LIMIT :lim
                """),
                {"bid": str(book_id), "lim": limit},
            ).fetchall()
        else:
            rows = self.session.execute(
                text("""
                    SELECT command_id, type, idempotency_key, status,
                        actor_id, actor_display_name, book_id, reason,
                        expected_version, payload_json, result_reference,
                        failure_code, failure_message, requested_at,
                        started_at, finished_at
                    FROM ops.command
                    ORDER BY requested_at DESC LIMIT :lim
                """),
                {"lim": limit},
            ).fetchall()
        return [self._row_to_command(r) for r in rows]

    def queue_command(self, command_id: UUID) -> None:
        self.session.execute(
            text("UPDATE ops.command SET status = :s WHERE command_id = :cid"),
            {"s": CommandStatus.QUEUED.value, "cid": str(command_id)},
        )

    def get_command_by_idempotency(
        self, actor_id: str, command_type: str, idempotency_key: str
    ) -> Command | None:
        row = self.session.execute(
            text("""
                SELECT command_id, type, idempotency_key, status,
                    actor_id, actor_display_name, book_id, reason,
                    expected_version, payload_json, result_reference,
                    failure_code, failure_message, requested_at,
                    started_at, finished_at
                FROM ops.command
                WHERE actor_id = :aid AND type = :type AND idempotency_key = :ik
            """),
            {"aid": actor_id, "type": command_type, "ik": idempotency_key},
        ).fetchone()
        if row is None:
            return None
        return self._row_to_command(row)

    def count_pending_commands(self) -> int:
        row = self.session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM ops.command WHERE status IN ('requested', 'queued', 'running')"  # noqa: E501
            )
        ).fetchone()
        return row._mapping["cnt"] if row else 0

    # --- Operator command handlers ---

    def cancel_order(self, order_id: UUID, reason: str | None = None) -> None:
        from alpha_quant.contracts.operational import OrderStatus

        status = OrderStatus.CANCELLED.value
        self.session.execute(
            text(
                "UPDATE trade.paper_order SET status = :s WHERE order_id = :oid AND status IN ('pending', 'open', 'submitted')"
            ),
            {"s": status, "oid": str(order_id)},
        )
        self.session.execute(
            text("""
                INSERT INTO audit.audit_event
                    (event_id, decision_run_id, event_type, payload_json, created_at)
                VALUES (:eid, :rid, :et, :pj, :now)
            """),
            {
                "eid": str(uuid4()),
                "rid": None,
                "et": "order.cancelled",
                "pj": json.dumps({"order_id": str(order_id), "reason": reason or ""}),
                "now": datetime.now(UTC),
            },
        )

    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        book_id: UUID,
        limit_price: float | None = None,
        decision_id: str | None = None,
    ) -> str:
        from uuid import uuid5

        from alpha_quant.contracts.operational import OrderStatus

        # Use deterministic security_id (uuid5 DNS hash of symbol) so orders,
        # fills, and position_current all use the same ID regardless of
        # security_reference duplicates.
        _sec_ns = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        security_id = str(uuid5(_sec_ns, symbol + ".com"))

        order_id = str(uuid4())
        status = OrderStatus.PENDING.value
        self.session.execute(
            text("""
                INSERT INTO trade.paper_order
                    (order_id, decision_run_id, portfolio_book_id, security_id,
                     symbol, side, quantity, status, idempotency_key,
                     limit_price, submitted_at)
                VALUES
                    (:oid, :rid, :pbid, :sid,
                     :sym, :sd, :qty, :st, :ik,
                     :lp, :now)
            """),
            {
                "oid": order_id,
                "rid": decision_id if decision_id else None,
                "pbid": str(book_id),
                "sid": security_id,
                "sym": symbol,
                "sd": side,
                "qty": str(quantity),
                "st": status,
                "ik": str(uuid4()),
                "lp": str(limit_price) if limit_price is not None else None,
                "now": datetime.now(UTC),
            },
        )
        return order_id

    def update_position_stop(self, symbol: str, stop_price: float, book_id: UUID) -> None:
        self.session.execute(
            text("""
                UPDATE projection.position_current
                SET stop_price = :sp
                WHERE symbol = :sym AND book_id = :bid
            """),
            {"sp": str(stop_price), "sym": symbol, "bid": str(book_id)},
        )

    def mark_operator_excluded(self, decision_id: str, reason: str | None = None) -> None:
        self.session.execute(
            text("""
                UPDATE run.candidate_evaluation
                SET blocked = TRUE, block_reason = :br
                WHERE candidate_id = :cid
            """),
            {"cid": decision_id, "br": reason or "operator_excluded"},
        )

    def _row_to_command(self, r: Any) -> Command:
        return Command(
            command_id=UUID(r._mapping["command_id"]),
            type=r._mapping["type"],
            idempotency_key=r._mapping["idempotency_key"],
            status=CommandStatus(r._mapping["status"]),
            actor_id=r._mapping["actor_id"],
            actor_display_name=r._mapping["actor_display_name"],
            book_id=UUID(r._mapping["book_id"]) if r._mapping.get("book_id") else None,
            reason=r._mapping.get("reason"),
            expected_version=r._mapping.get("expected_version"),
            payload_json=r._mapping["payload_json"],
            result_reference=r._mapping.get("result_reference"),
            failure_code=r._mapping.get("failure_code"),
            failure_message=r._mapping.get("failure_message"),
            requested_at=r._mapping["requested_at"],
            started_at=r._mapping.get("started_at"),
            finished_at=r._mapping.get("finished_at"),
        )

    # --- Helpers ---

    def _row_to_decision_run(self, r: Any) -> DecisionRun:
        return DecisionRun(
            decision_run_id=UUID(r._mapping["decision_run_id"]),
            run_key=r._mapping["run_key"],
            run_kind=RunKind(r._mapping["run_kind"]),  # type: ignore[arg-type]
            status=RunStatus(r._mapping["status"]),
            strategy_version_id=UUID(r._mapping["strategy_version_id"]),
            portfolio_book_id=UUID(r._mapping["portfolio_book_id"]),
            decision_as_of=r._mapping["decision_as_of"],
            execution_as_of=r._mapping.get("execution_as_of"),
            resolved_snapshot_id=r._mapping["resolved_snapshot_id"],
            alpha_lake_api_version=r._mapping["alpha_lake_api_version"],
            alpha_lake_contract_version=r._mapping["alpha_lake_contract_version"],
            config_hash=r._mapping["config_hash"],
            request_hash=r._mapping["request_hash"],
            response_hash=r._mapping["response_hash"],
            started_at=r._mapping["started_at"],
            completed_at=r._mapping.get("completed_at"),
            failure_reason=r._mapping.get("failure_reason"),
        )

    # --- App config (mock mode etc.) ---

    def config_get(self, key: str, default: str | None = None) -> str | None:
        row = self.session.execute(
            text("SELECT value FROM ops.app_config WHERE key = :k"),
            {"k": key},
        ).one_or_none()
        return row._mapping["value"] if row else default

    def config_set(self, key: str, value: str) -> None:
        import json

        self.session.execute(
            text(
                """INSERT INTO ops.app_config (key, value, updated_at)
                   VALUES (:k, :v, NOW())
                   ON CONFLICT (key) DO UPDATE SET value = :v2, updated_at = NOW()"""
            ),
            {"k": key, "v": value, "v2": value},
        )
        self.session.execute(
            text(
                """INSERT INTO audit.audit_event (event_id, decision_run_id, event_type, payload_json, created_at)
                   VALUES (:eid, NULL, :etype, :pj, NOW())"""
            ),
            {
                "eid": str(uuid4()),
                "etype": f"config.{key}.changed",
                "pj": json.dumps({"key": key, "value": value}),
            },
        )

    # --- Row mappers ---

    @staticmethod
    def _row_to_scorecard(row: Any, session: Session) -> Scorecard:
        comp_rows = session.execute(
            text("""
                SELECT component_id, scorecard_id, name, category,
                       score, state, weight, passed, reason, details_json
                FROM run.scorecard_component
                WHERE scorecard_id = :sid
                ORDER BY name
            """),
            {"sid": row._mapping["scorecard_id"]},
        ).fetchall()

        components = [
            ScorecardComponent(
                name=r._mapping["name"],
                category=r._mapping["category"],
                score=float(r._mapping["score"]),
                state=r._mapping["state"],
                weight=float(r._mapping["weight"]),
                passed=r._mapping["passed"],
                reason=r._mapping["reason"] or "",
                details_json=r._mapping["details_json"],
            )
            for r in comp_rows
        ]

        return Scorecard(
            scorecard_id=row._mapping["scorecard_id"],
            decision_run_id=row._mapping["decision_run_id"],
            portfolio_book_id=row._mapping["portfolio_book_id"],
            symbol=row._mapping["symbol"],
            security_id=row._mapping["security_id"],
            as_of=row._mapping["as_of"],
            snapshot_id=row._mapping.get("snapshot_id"),
            facts_hash=row._mapping["facts_hash"],
            config_hash=row._mapping["config_hash"],
            strategy_version=row._mapping["strategy_version"],
            recommendation=row._mapping["recommendation"],
            confidence=float(row._mapping["confidence"]),
            total_score=float(row._mapping["total_score"]),
            data_quality=row._mapping["data_quality"],
            components=components,
            created_at=row._mapping["created_at"],
        )
