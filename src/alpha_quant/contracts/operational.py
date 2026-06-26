from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class RunKind(StrEnum):
    DAILY = "daily"
    BACKTEST = "backtest"
    REPLAY = "replay"


class RunStatus(StrEnum):
    RESERVED = "reserved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    HALTED = "halted"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"


class FillQuality(StrEnum):
    OPEN = "open"
    STOP = "stop"
    GAP = "gap"
    PARTIAL = "partial"


class HaltReason(StrEnum):
    DAILY_LOSS = "daily_loss"
    DRAWDOWN = "drawdown"
    STALENESS = "staleness"
    INVARIANT = "invariant"
    MANUAL = "manual"


@dataclass(frozen=True)
class Strategy:
    strategy_id: UUID
    name: str
    created_at: datetime


@dataclass(frozen=True)
class StrategyVersion:
    strategy_version_id: UUID
    strategy_id: UUID
    version_label: str
    config_json: str
    config_hash: str
    created_at: datetime


@dataclass(frozen=True)
class PortfolioBook:
    book_id: UUID
    name: str
    kind: str
    created_at: datetime


@dataclass(frozen=True)
class SecurityReference:
    security_id: UUID
    symbol: str
    display_name: str | None = None
    sector: str | None = None


@dataclass(frozen=True)
class ExecutionProfile:
    profile_id: UUID
    name: str
    slippage_bps: int
    spread_model: str


@dataclass(frozen=True)
class DecisionRun:
    decision_run_id: UUID
    run_key: str
    run_kind: RunKind
    status: RunStatus
    strategy_version_id: UUID
    portfolio_book_id: UUID
    decision_as_of: datetime
    execution_as_of: datetime | None
    resolved_snapshot_id: str
    alpha_lake_api_version: str
    alpha_lake_contract_version: str
    config_hash: str
    request_hash: str
    response_hash: str
    started_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class AlphaLakeManifest:
    manifest_id: UUID
    decision_run_id: UUID
    request_body: str
    response_body: str
    snapshot_id: str
    contract_version: str
    api_version: str
    request_hash: str
    response_hash: str
    created_at: datetime


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: UUID
    decision_run_id: UUID
    portfolio_book_id: UUID
    security_id: UUID
    symbol: str
    composite_score: Decimal
    regime: str
    blocked: bool
    block_reason: str | None = None
    gate_results: str = "{}"


@dataclass(frozen=True)
class PolicyEvaluation:
    evaluation_id: UUID
    candidate_id: UUID
    policy_name: str
    policy_version: str
    score: Decimal | None = None
    passed: bool | None = None
    reason: str | None = None
    details_json: str = "{}"


@dataclass(frozen=True)
class PaperOrder:
    order_id: UUID
    decision_run_id: UUID
    portfolio_book_id: UUID
    security_id: UUID
    symbol: str
    side: OrderSide
    quantity: Decimal
    status: OrderStatus
    idempotency_key: str
    limit_price: Decimal | None = None
    submitted_at: datetime | None = None
    filled_quantity: Decimal | None = None


@dataclass(frozen=True)
class PaperFill:
    fill_id: UUID
    order_id: UUID
    security_id: UUID
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fill_key: str
    quality: FillQuality = FillQuality.OPEN
    fee: Decimal = Decimal("0")
    booked_at: datetime | None = None


@dataclass(frozen=True)
class CashLedgerEntry:
    entry_id: UUID
    portfolio_book_id: UUID
    fill_id: UUID | None = None
    amount: Decimal = Decimal("0")
    currency: str = "USD"
    reason: str = ""
    booked_at: datetime | None = None


@dataclass(frozen=True)
class CorporateActionBooking:
    booking_id: UUID
    portfolio_book_id: UUID
    security_id: UUID
    action_type: str
    effective_date: date
    ratio: Decimal | None = None
    amount: Decimal | None = None


@dataclass(frozen=True)
class PortfolioMark:
    mark_id: UUID
    portfolio_book_id: UUID
    effective_date: date
    cash: Decimal
    equity: Decimal
    gross_exposure: Decimal
    regime: str
    mark_as_of: datetime


@dataclass(frozen=True)
class PositionCurrent:
    book_id: UUID
    security_id: UUID
    symbol: str
    quantity: Decimal
    avg_cost: Decimal
    current_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pl: Decimal | None = None
    stop_price: Decimal | None = None


@dataclass(frozen=True)
class PortfolioCurrent:
    book_id: UUID
    cash: Decimal
    equity: Decimal
    gross_exposure: Decimal
    regime: str
    updated_at: datetime


@dataclass(frozen=True)
class AuditEvent:
    event_id: UUID
    decision_run_id: UUID
    event_type: str
    payload_json: str
    created_at: datetime


@dataclass(frozen=True)
class RiskEvent:
    risk_event_id: UUID
    decision_run_id: UUID
    event_type: str
    severity: str
    details_json: str
    created_at: datetime


@dataclass(frozen=True)
class HaltTransition:
    halt_id: UUID
    portfolio_book_id: UUID
    reason: HaltReason
    details: str
    halted_at: datetime
    resumed_at: datetime | None = None


@dataclass(frozen=True)
class CurrentHalt:
    book_id: UUID
    halted: bool
    reason: HaltReason | None = None
    details: str | None = None
    halted_at: datetime | None = None


@dataclass(frozen=True)
class RunReservation:
    run_key: str
    run_kind: RunKind
    strategy_version_id: UUID
    portfolio_book_id: UUID
    decision_as_of: datetime
    resolved_snapshot_id: str
    alpha_lake_api_version: str
    alpha_lake_contract_version: str
    config_hash: str
    request_hash: str
    response_hash: str


@dataclass(frozen=True)
class DecisionBatch:
    decision_run_id: UUID
    candidates: list[CandidateEvaluation] = field(default_factory=list)
    policy_evals: list[PolicyEvaluation] = field(default_factory=list)


@dataclass(frozen=True)
class FillBookingCommand:
    order_id: UUID
    decision_run_id: UUID
    portfolio_book_id: UUID
    security_id: UUID
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fill_key: str
    idempotency_key: str
    quality: FillQuality = FillQuality.OPEN
    fee: Decimal = Decimal("0")
    reason: str = "execution"


@dataclass(frozen=True)
class FillBookingResult:
    fill_id: UUID
    fill_key: str
    already_booked: bool = False


@dataclass(frozen=True)
class HaltCommand:
    portfolio_book_id: UUID
    reason: HaltReason
    details: str


class CommandStatus(StrEnum):
    REQUESTED = "requested"
    VALIDATED = "validated"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Command:
    command_id: UUID
    type: str
    idempotency_key: str
    status: CommandStatus
    actor_id: str
    actor_display_name: str
    book_id: UUID | None = None
    reason: str | None = None
    expected_version: int | None = None
    payload_json: str = "{}"
    result_reference: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    requested_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class CommandEnvelope:
    type: str
    idempotency_key: str
    actor_id: str
    actor_display_name: str
    book_id: UUID | None = None
    reason: str | None = None
    expected_version: int | None = None
    payload_json: str = "{}"


@dataclass(frozen=True)
class PortfolioState:
    book_id: UUID
    cash: Decimal
    positions: list[PositionCurrent]
    open_orders: list[PaperOrder]


@dataclass(frozen=True)
class ImmutableArtifact:
    key: str
    content_type: str
    body: str
    checksum_sha256: str | None = None


@dataclass(frozen=True)
class ArtifactReference:
    key: str
    bucket: str
    checksum_sha256: str | None = None
    size_bytes: int | None = None
