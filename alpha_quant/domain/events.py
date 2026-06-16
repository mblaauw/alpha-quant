"""Domain event types for the event-sourced pipeline log."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from alpha_quant.domain.models import Fill, Order


class BaseDomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str
    source: str
    event_type: str


class PipelineRunStarted(BaseDomainEvent):
    event_type: Literal["pipeline_run_started"] = "pipeline_run_started"
    mode: str


class PipelineRunCompleted(BaseDomainEvent):
    event_type: Literal["pipeline_run_completed"] = "pipeline_run_completed"
    duration_s: float
    status: str


class DataIngested(BaseDomainEvent):
    event_type: Literal["data_ingested"] = "data_ingested"
    connector: str
    symbol: str
    records: int


class DataQuarantined(BaseDomainEvent):
    event_type: Literal["data_quarantined"] = "data_quarantined"
    symbol: str
    reason: str
    detail: str = ""


class SourceDegraded(BaseDomainEvent):
    event_type: Literal["source_degraded"] = "source_degraded"
    source_name: str
    fallback: str


class StalenessHaltSet(BaseDomainEvent):
    event_type: Literal["staleness_halt_set"] = "staleness_halt_set"
    symbol: str
    hours_since_last: float


class IndicatorStateUpdated(BaseDomainEvent):
    event_type: Literal["indicator_state_updated"] = "indicator_state_updated"
    symbol: str
    indicator_count: int


class RegimeChanged(BaseDomainEvent):
    event_type: Literal["regime_changed"] = "regime_changed"
    previous: str
    current: str


class CandidateScored(BaseDomainEvent):
    event_type: Literal["candidate_scored"] = "candidate_scored"
    symbol: str
    composite_score: float
    components: dict


class CandidateBlocked(BaseDomainEvent):
    event_type: Literal["candidate_blocked"] = "candidate_blocked"
    symbol: str
    reason: str
    gate: str


class CandidatePromoted(BaseDomainEvent):
    event_type: Literal["candidate_promoted"] = "candidate_promoted"
    symbol: str
    score: float
    target_weight: float


class OrderSimulated(BaseDomainEvent):
    event_type: Literal["order_simulated"] = "order_simulated"
    order: Order


class FillBooked(BaseDomainEvent):
    event_type: Literal["fill_booked"] = "fill_booked"
    fill: Fill


class StopAdjusted(BaseDomainEvent):
    event_type: Literal["stop_adjusted"] = "stop_adjusted"
    symbol: str
    old_stop: float
    new_stop: float


class PartialTaken(BaseDomainEvent):
    event_type: Literal["partial_taken"] = "partial_taken"
    symbol: str
    quantity: float
    price: float


class TimeStopTriggered(BaseDomainEvent):
    event_type: Literal["time_stop_triggered"] = "time_stop_triggered"
    symbol: str
    days_held: int


class DrawdownLadderTripped(BaseDomainEvent):
    event_type: Literal["drawdown_ladder_tripped"] = "drawdown_ladder_tripped"
    drawdown_pct: float
    action: str


class BookMarked(BaseDomainEvent):
    event_type: Literal["book_marked"] = "book_marked"
    book: str
    equity: float


class ConsistencyViolation(BaseDomainEvent):
    event_type: Literal["consistency_violation"] = "consistency_violation"
    check: str
    detail: str


class ErrorOccurred(BaseDomainEvent):
    event_type: Literal["error_occurred"] = "error_occurred"
    error: str
    context: dict = Field(default_factory=dict)


class PipelineStepCompleted(BaseDomainEvent):
    event_type: Literal["pipeline_step_completed"] = "pipeline_step_completed"
    step_name: str
    duration_s: float
    symbols_processed: int = 0
    items_processed: int = 0


DomainEvent = Annotated[
    PipelineRunStarted
    | PipelineRunCompleted
    | DataIngested
    | DataQuarantined
    | SourceDegraded
    | StalenessHaltSet
    | IndicatorStateUpdated
    | RegimeChanged
    | CandidateScored
    | CandidateBlocked
    | CandidatePromoted
    | OrderSimulated
    | FillBooked
    | StopAdjusted
    | PartialTaken
    | TimeStopTriggered
    | DrawdownLadderTripped
    | BookMarked
    | ConsistencyViolation
    | ErrorOccurred
    | PipelineStepCompleted,
    Field(discriminator="event_type"),
]
