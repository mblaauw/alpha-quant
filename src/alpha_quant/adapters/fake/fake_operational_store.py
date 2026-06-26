from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from alpha_quant.contracts.operational import (
    AuditEvent,
    CandidateEvaluation,
    CurrentHalt,
    DecisionBatch,
    DecisionRun,
    FillBookingCommand,
    FillBookingResult,
    HaltCommand,
    PolicyEvaluation,
    PortfolioBook,
    PortfolioMark,
    PortfolioState,
    PositionCurrent,
    RunReservation,
    RunStatus,
    Strategy,
)


class FakeOperationalStore:
    def __init__(self, run_id: UUID | None = None) -> None:
        self.runs: dict[str, DecisionRun] = {}
        self.candidates: list[CandidateEvaluation] = []
        self.policy_evals: list[PolicyEvaluation] = []
        self.fills: list[FillBookingCommand] = []
        self.portfolio_state: PortfolioState | None = None
        self.halt: CurrentHalt | None = None
        self.marks: list[PortfolioMark] = []
        self._next_run_id = run_id or uuid4()

    def reserve_run(self, request: RunReservation) -> DecisionRun:
        run = DecisionRun(
            decision_run_id=self._next_run_id,
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
            started_at=datetime.now(UTC),
        )
        self.runs[run.run_key] = run
        return run

    def start_run(self, run_id: UUID) -> None:
        for run in self.runs.values():
            if run.decision_run_id == run_id:
                object.__setattr__(run, "status", RunStatus.RUNNING)
                return

    def complete_run(self, run_id: UUID, status: str, failure_reason: str | None = None) -> None:
        for run in self.runs.values():
            if run.decision_run_id == run_id:
                object.__setattr__(run, "status", RunStatus(status))
                object.__setattr__(run, "completed_at", datetime.now(UTC))
                object.__setattr__(run, "failure_reason", failure_reason)
                return

    def commit_decision_batch(self, batch: DecisionBatch) -> None:
        for cand in batch.candidates:
            self.candidates.append(cand)
        for pe in batch.policy_evals:
            self.policy_evals.append(pe)

    def book_fill(self, command: FillBookingCommand) -> FillBookingResult:
        for existing in self.fills:
            if existing.fill_key == command.fill_key:
                return FillBookingResult(
                    fill_id=uuid4(), fill_key=command.fill_key, already_booked=True
                )
        self.fills.append(command)
        return FillBookingResult(fill_id=uuid4(), fill_key=command.fill_key, already_booked=False)

    def load_portfolio(self, book_id: UUID) -> PortfolioState:
        if self.portfolio_state is not None:
            return self.portfolio_state
        return PortfolioState(book_id=book_id, cash=0, positions=[], open_orders=[])

    def save_portfolio_mark(self, mark: PortfolioMark) -> None:
        self.marks.append(mark)

    def set_halt(self, command: HaltCommand) -> None:
        self.halt = CurrentHalt(
            book_id=command.portfolio_book_id,
            halted=True,
            reason=command.reason,
            details=command.details,
            halted_at=datetime.now(UTC),
        )

    def clear_halt(self, book_id: UUID) -> None:
        self.halt = None

    def current_halt(self, book_id: UUID) -> CurrentHalt | None:
        return self.halt

    def rebuild_projections(self, book_id: UUID) -> None:
        pass

    def list_strategies(self) -> list[Strategy]:
        return []

    def list_books(self) -> list[PortfolioBook]:
        return []

    def list_decision_runs(self, book_id: UUID, limit: int = 20) -> list[DecisionRun]:
        return list(self.runs.values())[:limit]

    def get_run_by_key(self, run_key: str) -> DecisionRun | None:
        return self.runs.get(run_key)

    def list_candidates(self, run_id: UUID, limit: int = 100) -> list[CandidateEvaluation]:
        return self.candidates[:limit]

    def list_policy_evals(self, run_id: UUID, limit: int = 500) -> list[PolicyEvaluation]:
        return self.policy_evals[:limit]

    def list_audit_events(self, run_id: UUID, limit: int = 200) -> list[AuditEvent]:
        return []

    def list_positions(self, book_id: UUID) -> list[PositionCurrent]:
        return []
