from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from alpha_quant.contracts.operational import (
    AuditEvent,
    CandidateEvaluation,
    Command,
    CommandEnvelope,
    CommandStatus,
    CurrentHalt,
    DecisionBatch,
    DecisionRun,
    FillBookingCommand,
    FillBookingResult,
    HaltCommand,
    OrderSide,
    PolicyEvaluation,
    PortfolioBook,
    PortfolioMark,
    PortfolioState,
    PositionCurrent,
    RiskEvent,
    RunReservation,
    RunStatus,
    Strategy,
)
from alpha_quant.domain.advice import AdviceArtifact, OperatorOverride
from alpha_quant.domain.risk import RiskPolicy
from alpha_quant.domain.scorecard import Scorecard, ScorecardComponent


class _FakeSession:
    """Minimal SQLAlchemy-like session that handles security_reference lookups."""

    def __init__(self, security_refs: dict[str, str]) -> None:
        self._security_refs = security_refs

    def execute(
        self,
        statement: Any,
        params: dict[str, Any] | None = None,
    ) -> _FakeResult:
        sql = str(statement)
        params = params or {}
        if "SELECT security_id FROM core.security_reference" in sql:
            symbol = params.get("sym", "")
            security_id = self._security_refs.get(symbol)
            return _FakeResult(security_id)
        if "INSERT INTO core.security_reference" in sql:
            sid = str(params.get("sid", ""))
            sym = str(params.get("sym", ""))
            if sym and sym not in self._security_refs:
                self._security_refs[sym] = sid
        return _FakeResult(None)


class _FakeResult:
    def __init__(self, security_id: str | None) -> None:
        self._security_id = security_id

    def fetchone(self) -> _FakeResult | None:
        if self._security_id is not None:
            return self
        return None

    @property
    def _mapping(self) -> dict[str, str]:
        return {"security_id": self._security_id} if self._security_id else {}


class FakeOperationalStore:
    def __init__(self) -> None:
        self._runs: dict[UUID, DecisionRun] = {}
        self._runs_by_key: dict[str, DecisionRun] = {}
        self._candidates: dict[UUID, CandidateEvaluation] = {}
        self._candidates_by_run: dict[UUID, list[CandidateEvaluation]] = {}
        self._policy_evals: dict[UUID, PolicyEvaluation] = {}
        self._policy_evals_by_candidate: dict[UUID, list[PolicyEvaluation]] = {}
        self._fills: dict[str, FillBookingResult] = {}
        self._fill_records: list[dict[str, Any]] = []
        self._cash_ledger: list[dict[str, Any]] = []
        self._portfolio_marks: list[PortfolioMark] = []
        self._halts: dict[UUID, CurrentHalt] = {}
        self._strategies: list[Strategy] = []
        self._books: list[PortfolioBook] = []
        self._positions_cache: dict[tuple[UUID, UUID], PositionCurrent] = {}
        self._audit_events: list[AuditEvent] = []
        self._scorecards: dict[str, Scorecard] = {}
        self._scorecard_components: dict[str, list[ScorecardComponent]] = {}
        self._advice_artifacts: dict[str, AdviceArtifact] = {}
        self._operator_overrides: dict[str, OperatorOverride] = {}
        self._risk_methods: list[dict[str, Any]] = []
        self._book_risk_profiles: dict[UUID, dict[str, Any]] = {}
        self._position_risks: dict[tuple[UUID, str], dict[str, Any]] = {}
        self._commands: dict[UUID, Command] = {}
        self._config: dict[str, str] = {}
        self._security_refs: dict[str, str] = {}
        self._risk_policies: dict[str, RiskPolicy] = {}
        self._risk_events: list[RiskEvent] = []

    @property
    def session(self) -> _FakeSession:
        return _FakeSession(self._security_refs)

    # --- Run lifecycle ---

    def reserve_run(self, request: RunReservation) -> DecisionRun:
        run_id = uuid4()
        now = datetime.now(UTC)
        run = DecisionRun(
            decision_run_id=run_id,
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
        self._runs[run_id] = run
        self._runs_by_key[request.run_key] = run
        return run

    def start_run(self, run_id: UUID) -> None:
        run = self._runs.get(run_id)
        if run is not None:
            updated = replace(run, status=RunStatus.RUNNING)
            self._runs[run_id] = updated
            self._runs_by_key[updated.run_key] = updated

    def complete_run(self, run_id: UUID, status: str, failure_reason: str | None = None) -> None:
        run = self._runs.get(run_id)
        if run is not None:
            updated = replace(
                run,
                status=RunStatus(status),
                completed_at=datetime.now(UTC),
                failure_reason=failure_reason,
            )
            self._runs[run_id] = updated
            self._runs_by_key[updated.run_key] = updated

    # --- Decision batch ---

    def commit_decision_batch(self, batch: DecisionBatch) -> None:
        for cand in batch.candidates:
            self._candidates[cand.candidate_id] = cand
            self._candidates_by_run.setdefault(batch.decision_run_id, []).append(cand)
        for pe in batch.policy_evals:
            self._policy_evals[pe.evaluation_id] = pe
            self._policy_evals_by_candidate.setdefault(pe.candidate_id, []).append(pe)

    # --- Fills ---

    def book_fill(self, command: FillBookingCommand) -> FillBookingResult:
        existing = next(
            (f for f in self._fill_records if f["fill_key"] == command.fill_key),
            None,
        )
        if existing is not None:
            return FillBookingResult(
                fill_id=existing["fill_id"],
                fill_key=existing["fill_key"],
                already_booked=True,
            )

        fill_id = uuid4()
        now = datetime.now(UTC)

        side_sign = -1 if command.side == OrderSide.BUY else 1
        cash_amount = side_sign * command.price * command.quantity - command.fee

        self._fill_records.append(
            {
                "fill_id": fill_id,
                "order_id": command.order_id,
                "security_id": command.security_id,
                "symbol": command.symbol,
                "side": command.side,
                "quantity": command.quantity,
                "price": command.price,
                "fill_key": command.fill_key,
                "quality": command.quality,
                "fee": command.fee,
                "booked_at": now,
            }
        )
        self._cash_ledger.append(
            {
                "entry_id": uuid4(),
                "portfolio_book_id": command.portfolio_book_id,
                "fill_id": fill_id,
                "amount": cash_amount,
                "currency": "USD",
                "reason": command.reason,
                "booked_at": now,
            }
        )
        return FillBookingResult(
            fill_id=fill_id,
            fill_key=command.fill_key,
            already_booked=False,
        )

    # --- Portfolio ---

    def load_portfolio(self, book_id: UUID) -> PortfolioState:
        total_cash = Decimal("0")
        for entry in self._cash_ledger:
            if entry["portfolio_book_id"] == book_id:
                total_cash += entry["amount"]

        positions = [
            pos
            for pos in self._positions_cache.values()
            if pos.book_id == book_id and pos.quantity != Decimal("0")
        ]

        return PortfolioState(
            book_id=book_id,
            cash=total_cash,
            positions=positions,
            open_orders=[],
        )

    def save_portfolio_mark(self, mark: PortfolioMark) -> None:
        existing = None
        for i, m in enumerate(self._portfolio_marks):
            if (
                m.portfolio_book_id == mark.portfolio_book_id
                and m.effective_date == mark.effective_date
            ):
                existing = i
                break
        if existing is not None:
            self._portfolio_marks[existing] = mark
        else:
            self._portfolio_marks.append(mark)

    # --- Halts ---

    def set_halt(self, command: HaltCommand) -> None:
        now = datetime.now(UTC)
        self._halts[command.portfolio_book_id] = CurrentHalt(
            book_id=command.portfolio_book_id,
            halted=True,
            reason=command.reason,
            details=command.details,
            halted_at=now,
        )

    def clear_halt(self, book_id: UUID) -> None:
        existing = self._halts.get(book_id)
        if existing is not None:
            self._halts[book_id] = replace(existing, halted=False)

    def current_halt(self, book_id: UUID) -> CurrentHalt | None:
        return self._halts.get(book_id)

    # --- Projections ---

    def rebuild_projections(self, book_id: UUID) -> None:
        self._positions_cache = {k: v for k, v in self._positions_cache.items() if k[0] != book_id}

        by_sec: dict[UUID, dict[str, Any]] = {}
        for fill in self._fill_records:
            sid = fill["security_id"]
            qty = fill["quantity"]
            price = fill["price"]
            side = fill["side"]

            if sid not in by_sec:
                by_sec[sid] = {
                    "security_id": sid,
                    "symbol": fill["symbol"],
                    "net_qty": Decimal("0"),
                    "buy_qty": Decimal("0"),
                    "buy_cost": Decimal("0"),
                    "last_price": price,
                }

            entry = by_sec[sid]
            if side == OrderSide.BUY:
                entry["net_qty"] += qty
                entry["buy_qty"] += qty
                entry["buy_cost"] += price * qty
            else:
                entry["net_qty"] -= qty
            entry["last_price"] = price

        for sid, data in by_sec.items():
            if data["net_qty"] == Decimal("0"):
                continue
            avg_cost = (
                data["buy_cost"] / data["buy_qty"]
                if data["buy_qty"] > Decimal("0")
                else Decimal("0")
            )
            current_price = data["last_price"]
            market_value = data["net_qty"] * current_price
            unrealized_pl = Decimal("0")
            if data["net_qty"] > Decimal("0"):
                unrealized_pl = (current_price - avg_cost) * data["net_qty"]

            self._positions_cache[(book_id, sid)] = PositionCurrent(
                book_id=book_id,
                security_id=sid,
                symbol=data["symbol"],
                quantity=data["net_qty"],
                avg_cost=avg_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pl=unrealized_pl,
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
        stored = scorecard.model_copy(
            update={
                "scorecard_id": scorecard_id,
                "decision_run_id": decision_run_id,
                "created_at": now,
            }
        )
        self._scorecards[scorecard_id] = stored
        self._scorecard_components[scorecard_id] = list(scorecard.components)
        return scorecard_id

    def load_scorecard(self, scorecard_id: str) -> Scorecard | None:
        return self._scorecards.get(scorecard_id)

    def load_scorecards_for_run(self, run_id: str) -> list[Scorecard]:
        return [sc for sc in self._scorecards.values() if sc.decision_run_id == run_id]

    # --- Advice ---

    def save_advice_artifact(self, advice: AdviceArtifact) -> str:
        advice_id = str(uuid4())
        stored = advice.model_copy(update={"advice_id": advice_id, "created_at": datetime.now(UTC)})
        self._advice_artifacts[advice_id] = stored
        return advice_id

    # --- Operator Overrides ---

    def save_operator_override(self, override: OperatorOverride) -> str:
        override_id = str(uuid4())
        stored = override.model_copy(
            update={"override_id": override_id, "created_at": datetime.now(UTC)}
        )
        self._operator_overrides[override_id] = stored
        return override_id

    # --- Risk Methods ---

    def list_risk_methods(self) -> list[dict[str, Any]]:
        return list(self._risk_methods)

    def set_book_risk_profile(self, book_id: UUID, risk_method_id: str, params_json: str) -> None:
        self._book_risk_profiles[book_id] = {
            "risk_method_id": risk_method_id,
            "params_json": params_json,
            "updated_at": datetime.now(UTC),
        }

    def update_position_risk(
        self,
        book_id: UUID,
        security_id: str,
        stop_price: float | None = None,
        trail_price: float | None = None,
        risk_method_id: str | None = None,
        auto_trail_enabled: bool | None = None,
    ) -> None:
        key = (book_id, security_id)
        current = self._position_risks.get(key, {})
        if stop_price is not None:
            current["stop_price"] = stop_price
        if trail_price is not None:
            current["trail_price"] = trail_price
        if risk_method_id is not None:
            current["risk_method_id"] = risk_method_id
        if auto_trail_enabled is not None:
            current["auto_trail_enabled"] = auto_trail_enabled
        current.setdefault("auto_trail_enabled", True)
        current["last_adjusted_at"] = datetime.now(UTC)
        self._position_risks[key] = current

    # --- Queries ---

    def list_strategies(self) -> list[Strategy]:
        return list(self._strategies)

    def list_books(self) -> list[PortfolioBook]:
        return list(self._books)

    def list_decision_runs(self, book_id: UUID, limit: int = 20) -> list[DecisionRun]:
        runs = sorted(
            [r for r in self._runs.values() if r.portfolio_book_id == book_id],
            key=lambda r: r.started_at,
            reverse=True,
        )
        return runs[:limit]

    def get_run_by_key(self, run_key: str) -> DecisionRun | None:
        return self._runs_by_key.get(run_key)

    def list_candidates(self, run_id: UUID, limit: int = 100) -> list[CandidateEvaluation]:
        candidates = self._candidates_by_run.get(run_id, [])
        sorted_candidates = sorted(
            candidates,
            key=lambda c: c.composite_score,
            reverse=True,
        )
        return sorted_candidates[:limit]

    def list_policy_evals(self, run_id: UUID, limit: int = 500) -> list[PolicyEvaluation]:
        evals: list[PolicyEvaluation] = []
        for cand in self._candidates_by_run.get(run_id, []):
            evals.extend(self._policy_evals_by_candidate.get(cand.candidate_id, []))
        evals.sort(key=lambda e: e.policy_name or "")
        return evals[:limit]

    def list_audit_events(self, run_id: UUID, limit: int = 200) -> list[AuditEvent]:
        filtered = [e for e in self._audit_events if e.decision_run_id == run_id]
        filtered.sort(key=lambda e: e.created_at)
        return filtered[:limit]

    def list_positions(self, book_id: UUID) -> list[PositionCurrent]:
        return [
            pos
            for pos in self._positions_cache.values()
            if pos.book_id == book_id and pos.quantity != Decimal("0")
        ]

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
        self._commands[cmd.command_id] = cmd
        self._audit_events.append(
            AuditEvent(
                event_id=uuid4(),
                decision_run_id=UUID(int=0),
                event_type=f"command.{cmd.type}.requested",
                payload_json=(
                    f'{{"command_id":"{cmd.command_id}","type":"{cmd.type}","actor":"{cmd.actor_id}"}}'
                ),
                created_at=now,
            )
        )
        return cmd

    def claim_command(self) -> Command | None:
        sorted_cmds = sorted(
            self._commands.values(),
            key=lambda c: c.requested_at or datetime.min.replace(tzinfo=UTC),
        )
        for cmd in sorted_cmds:
            if cmd.status == CommandStatus.QUEUED:
                now = datetime.now(UTC)
                updated = replace(cmd, status=CommandStatus.RUNNING, started_at=now)
                self._commands[cmd.command_id] = updated
                return updated
        return None

    def complete_command(
        self,
        command_id: UUID,
        status: CommandStatus,
        result: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> None:
        cmd = self._commands.get(command_id)
        if cmd is not None:
            self._commands[command_id] = replace(
                cmd,
                status=status,
                finished_at=datetime.now(UTC),
                result_reference=result,
                failure_code=failure_code,
                failure_message=failure_message,
            )

    def get_command(self, command_id: UUID) -> Command | None:
        return self._commands.get(command_id)

    def list_commands(self, book_id: UUID | None = None, limit: int = 50) -> list[Command]:
        cmds = list(self._commands.values())
        if book_id is not None:
            cmds = [c for c in cmds if c.book_id == book_id]
        cmds.sort(key=lambda c: c.requested_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return cmds[:limit]

    def queue_command(self, command_id: UUID) -> None:
        cmd = self._commands.get(command_id)
        if cmd is not None:
            self._commands[command_id] = replace(cmd, status=CommandStatus.QUEUED)

    def get_command_by_idempotency(
        self, actor_id: str, command_type: str, idempotency_key: str
    ) -> Command | None:
        for cmd in self._commands.values():
            if (
                cmd.actor_id == actor_id
                and cmd.type == command_type
                and cmd.idempotency_key == idempotency_key
            ):
                return cmd
        return None

    def count_pending_commands(self) -> int:
        return sum(
            1
            for cmd in self._commands.values()
            if cmd.status in (CommandStatus.REQUESTED, CommandStatus.QUEUED, CommandStatus.RUNNING)
        )

    # --- Operator command handlers ---

    def cancel_order(self, order_id: UUID, reason: str | None = None) -> None:

        self._audit_events.append(
            AuditEvent(
                event_id=uuid4(),
                decision_run_id=UUID(int=0),
                event_type="order.cancelled",
                payload_json=f'{{"order_id": "{order_id}", "reason": "{reason or ""}"}}',
                created_at=datetime.now(UTC),
            )
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
        return str(uuid4())

    def update_position_stop(self, symbol: str, stop_price: float, book_id: UUID) -> None:
        for key, pos in self._positions_cache.items():
            if key[0] == book_id and pos.symbol == symbol:
                self._positions_cache[key] = replace(pos, stop_price=Decimal(str(stop_price)))
                break

    def mark_operator_excluded(self, decision_id: str, reason: str | None = None) -> None:
        for cand_id, cand in self._candidates.items():
            if str(cand_id) == decision_id:
                self._candidates[cand_id] = replace(
                    cand,
                    blocked=True,
                    block_reason=reason or "operator_excluded",
                )
                break

    # --- App config ---

    def config_get(self, key: str, default: str | None = None) -> str | None:
        return self._config.get(key, default)

    def config_set(self, key: str, value: str) -> None:
        self._config[key] = value
        self._audit_events.append(
            AuditEvent(
                event_id=uuid4(),
                decision_run_id=UUID(int=0),
                event_type=f"config.{key}.changed",
                payload_json=json.dumps({"key": key, "value": value}),
                created_at=datetime.now(UTC),
            )
        )

    # --- Risk Policy ---

    def load_risk_policy(self, version_label: str = "default") -> RiskPolicy | None:
        return self._risk_policies.get(version_label)

    def save_risk_policy_version(self, policy: RiskPolicy) -> None:
        self._risk_policies[policy.version_label] = policy

    def write_risk_event(self, event: RiskEvent) -> None:
        self._risk_events.append(event)
